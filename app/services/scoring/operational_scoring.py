"""Configured RADAR C-07->scoring->77/78 production assembly.





Calculates scores from actual grid_feature and reviewer-confirmed C-08 rows.


Never substitutes unreviewed type-rule predictions for human decisions.


"""


from __future__ import annotations





from datetime import date


import hashlib


import json


import pandas as pd


import numpy as np





from app.services.scoring.approved_inputs import InputBlocked, aggregate_reviewed_complaints, load_approved_policy, read_approved_policy_document


from app.services.scoring.calculation import Policy, FEATURES, DOMAINS, calculate, normalize, rank_scores


from app.services.scoring.official_pipeline import OfficialInputs, run_official_pipeline


from app.services.scoring.b02_policy_contract import validate_policy_document


from app.services.scoring.setting_links import prepare_references


from app.services.scoring.d05_conditions import evaluate_d05, validate_d05_rule, verify_d05_persisted_conditions








def assemble_official_score(*, grid_rows: list[dict], reviewed_rows: list[dict],


                            start: date, end: date, policy_document: dict):


    """Generate actual scored candidates and five detail fields from approved config.





    The policy document must explicitly define complaint combine mode, strength,


    selection, confidence rules, and accident-exclusion rules. None are inferred.


    """


    if not isinstance(policy_document, dict):


        raise InputBlocked('POLICY_DOCUMENT_REQUIRED')


    # B02 v1 is immutable and internal-demo only. For a separately approved


    # non-v1 policy, validation is against its own SHA-bound document and 62 row.


    if policy_document.get('policy_authority') == 'RADAR_TEAM_INTERNAL_ONLY_NOT_SEONGNAM_CITY':


        validate_policy_document(policy_document, start=start, end=end)


    score_config = policy_document.get('policy', policy_document)


    policy = Policy(**{k:score_config[k] for k in


                      ('label','normalization','observation','domain_weights','accident_reduce','missing')})


    policy.validate()


    for field in ('complaint_mode','complaint_strength','confidence_thresholds',


                  'accident_exclusion','selection_min_score'):


        if field not in policy_document:


            raise InputBlocked('MISSING_APPROVED_POLICY_FIELD:' + field)


    mode = policy_document['complaint_mode']


    strength = float(policy_document['complaint_strength'])


    if mode not in ('independent','inside_hazard','bonus') or not 0 <= strength <= 1:


        raise InputBlocked('INVALID_COMPLAINT_COMBINATION')


    bounds = policy_document['confidence_thresholds']


    if (not isinstance(bounds, dict) or set(bounds) != {'high','medium'} or


            not 0 <= float(bounds['medium']) < float(bounds['high']) <= 1):


        raise InputBlocked('INVALID_CONFIDENCE_POLICY')


    if policy_document['accident_exclusion'] != 'reweight_observed_nonaccident':


        raise InputBlocked('UNSUPPORTED_ACCIDENT_EXCLUSION_POLICY')


    minimum = policy_document['selection_min_score']


    if isinstance(minimum,bool) or not isinstance(minimum,(int,float)) or not 0 <= minimum <= 100:


        raise InputBlocked('INVALID_SELECTION_POLICY')


    # D-05 thresholds must be present in the immutable, independently approved


    # policy document. Existing 62/1 does not acquire approval by this change.


    d05_rule = validate_d05_rule(policy_document.get('d05_rule'))


    if not grid_rows:


        raise InputBlocked('NO_GRID_DATA')


    grid=pd.DataFrame(grid_rows)


    required={'ID_gid','id_gu','ext_survey_scope_obstacle',*FEATURES}


    if not required <= set(grid):


        raise InputBlocked('GRID_FIELDS_MISSING:'+','.join(sorted(required-set(grid))))


    if grid.ID_gid.isna().any() or grid.ID_gid.duplicated().any():


        raise InputBlocked('DUPLICATE_OR_NULL_GIDS')


    grid=grid.sort_values('ID_gid').reset_index(drop=True)


    gid_set=set(grid.ID_gid.astype(str))


    counts=aggregate_reviewed_complaints(reviewed_rows,start=start,end=end,gids=gid_set)


    if any(r['classification_status'] != 'COMPLETE' for r in counts):


        raise InputBlocked('UNRESOLVED_COMPLAINTS_REQUIRE_EXPLICIT_EXCLUSION_POLICY')


    indexed=pd.DataFrame(counts).set_index('gid').loc[grid.ID_gid.astype(str)]


    base, domains, contributions, states=calculate(grid,policy)


    signal=normalize(indexed.relevant_count.reset_index(drop=True),policy.normalization)


    score=base.score.reset_index(drop=True).astype(float)


    hazard=domains['hazard'].reset_index(drop=True).astype(float)


    if mode=='independent':


        final=(1-strength)*score+100*strength*signal


    elif mode=='inside_hazard':


        final=score+100*policy.domain_weights['hazard']*strength*(signal-hazard)
        if policy_document.get('inside_hazard_unobserved') == 'keep_base_no_complaint_adjustment':
            # Missing observation is NOT zero risk. Do not alter hazard/domain status.
            final=final.where(hazard.notna(), score)


    else:


        final=(score+100*strength*signal).clip(upper=100)


    final=final.where(signal.notna()&score.notna())


    if final.notna().sum()!=len(grid):


        raise InputBlocked('UNSCORED_GRIDS_REQUIRE_EXPLICIT_POLICY')


    rank=rank_scores(final,grid.ID_gid)


    candidates=[]; evidence={}


    for i,gid in enumerate(grid.ID_gid.astype(str)):


        vals=domains.iloc[i]


        nonacc={k:float(v) for k,v in vals.items() if k!='accident' and pd.notna(v)}


        denom=sum(policy.domain_weights[k] for k in nonacc)


        if denom<=0:


            raise InputBlocked('ACCIDENT_EXCLUDED_SCORE_UNAVAILABLE:'+gid)


        # Recompute the final combination with accident removed from the base.


        base_without=100*sum(nonacc[k]*policy.domain_weights[k] for k in nonacc)/denom


        if mode=='independent':


            without=(1-strength)*base_without+100*strength*float(signal.iloc[i])


        elif mode=='inside_hazard':


            if pd.isna(hazard.iloc[i]):
                if policy_document.get('inside_hazard_unobserved') != 'keep_base_no_complaint_adjustment':
                    raise InputBlocked('UNOBSERVED_HAZARD_POLICY_REQUIRED')
                without=base_without
            else:
                without=base_without+100*(policy.domain_weights['hazard']/denom)*strength*(float(signal.iloc[i])-float(hazard.iloc[i]))


        else:


            without=min(100,base_without+100*strength*float(signal.iloc[i]))


        coverage=float(base.coverage_fraction.iloc[i])


        grade='HIGH' if coverage>=float(bounds['high']) else ('MEDIUM' if coverage>=float(bounds['medium']) else 'LOW')


        score_value=round(float(final.iloc[i]),4)


        cnt=indexed.iloc[i]


        d05 = evaluate_d05({k:(None if pd.isna(vals[k]) else float(vals[k]))


                            for k in ('hazard','exposure','vulnerability')}, d05_rule)


        candidates.append({'gid':gid,'official_score':score_value,'rank_no':int(rank.rank_no.iloc[i]),


            'selected_yn':'Y' if score_value>=minimum else 'N',


            'complaint_cnt':int(cnt.relevant_count),'complaint_cnt_excl_low':int(cnt.count_excl_low),


            'calculation_status':'OFFICIAL','input_status':'VERIFIED_CLASSIFIED',


            'classification_status':cnt.classification_status,'source_kind':'VERIFIED_CLASSIFIED',


            **d05,'note':None})


        evidence[gid]={


            'domain_scores':{k:(None if pd.isna(v) else round(float(v)*100,6)) for k,v in vals.items()},


            'indicator_contributions':{k:(None if pd.isna(v) else round(float(v),6)) for k,v in contributions.iloc[i].items()},


            'unevaluated_reasons':{k:str(states.iloc[i][k]) for k in FEATURES if states.iloc[i][k]!='RECORD_VALUE'},


            'confidence_grade':grade,


            'score_excluding_accidents':round(float(without),4),


            'exclusion_reasons': [],


            # Net effect relative to identical inputs scored without the complaint signal.


            # This value can be negative for independent/inside_hazard modes.


            'complaint_contribution':round(float(final.iloc[i])-float(score.iloc[i]),6),


            'policy_version':policy.label}


    return tuple(candidates),evidence








def run_from_live_rows(*, setting_version_id:int, evidence_dir:str, build_id:str,


                       start:date,end:date,grid_rows:list[dict],reviewed_rows:list[dict],


                       authorized_by:str,approval_reference:str,explicit_db_write_approval:bool,


                       read_only=None,connection_factory=None,


                       weight_setting_version_id=None, threshold_setting_version_id=None,


                       priority_condition_setting_version_id=None, existing_run_id:int|None=None, r02_full_source_input=None):


    # Approved 2022-2025 complaint window must always use the signed native build
    # and its ten-exception disposition; reviewed JSON must not bypass this gate.
    if start.isoformat() == '2022-01-01' and end.isoformat() == '2025-12-31':
        if r02_full_source_input is None or not build_id.startswith('db59:'):
            raise InputBlocked('EXCEPTION10_NATIVE_APPROVED_BUILD_REQUIRED')
        from app.services.scoring.r02_exception10_policy import approved_exclusion_receipt
        if r02_full_source_input.audit.get('approved_exception_disposition') != approved_exclusion_receipt():
            raise InputBlocked('EXCEPTION10_APPROVED_RECEIPT_MISSING')

    if r02_full_source_input is not None and explicit_db_write_approval and not build_id.startswith('db59:'):


        raise InputBlocked('R02_FULL_SOURCE_OFFICIAL_WRITES_BLOCKED')


    if type(existing_run_id) is not int or existing_run_id <= 0:


        raise InputBlocked('D10_EXISTING_RUN_ID_REQUIRED')


    if existing_run_id == 1:
        raise InputBlocked('LEGACY_RUN1_OFFICIAL_ACCESS_BLOCKED')
    if read_only is None:


        from app.core.db import read_only


    settings=read_only('SELECT setting_version_id,setting_kind,version_label,content_ref,approval_status,approved_at,review_comment '


                       'FROM setting_version WHERE setting_version_id=%s',(setting_version_id,))


    if len(settings)!=1:raise InputBlocked('SETTING_NOT_FOUND')


    row=settings[0]


    # B02/62-1 remains an internal demo. A different, genuinely approved 62


    # row is read by its own SHA-256 and may define its own D05 thresholds.


    if setting_version_id == 1:


        from app.services.scoring.b02_policy_contract import read_immutable_document


        document, _b02_contract = read_immutable_document(evidence_dir, row)


        validate_policy_document(document, start=start, end=end, setting=row, require_simulated_origin=True)


    else:


        document = read_approved_policy_document(row, evidence_dir)


        if document.get('policy_authority') == 'RADAR_TEAM_INTERNAL_ONLY_NOT_SEONGNAM_CITY':


            raise InputBlocked('INTERNAL_DEMO_POLICY_CANNOT_BE_RELABELED')


        if (document.get('input_period_start') != start.isoformat() or


                document.get('input_period_end') != end.isoformat()):


            raise InputBlocked('APPROVED_POLICY_PERIOD_MISMATCH')


    references = prepare_references(read_only,


        (weight_setting_version_id, threshold_setting_version_id, priority_condition_setting_version_id),


        evidence_dir, document)


    policy=load_approved_policy(row,evidence_dir)


    digest=row['content_ref'][7:]
    if r02_full_source_input is not None and build_id.startswith('db59:'):
        from app.services.scoring.input_builds import verify_supplied_scoring_inputs
        verify_supplied_scoring_inputs(build_id=build_id,grids=grid_rows,source=reviewed_rows,
            policy_sha256=digest,setting_ids=(weight_setting_version_id,threshold_setting_version_id,
            priority_condition_setting_version_id),reader=read_only)



    scoring_reviewed_rows = reviewed_rows

    if r02_full_source_input is not None:

        from app.services.scoring.r02_full_source_quarantine import FullSourceR02

        if not isinstance(r02_full_source_input, FullSourceR02):

            raise InputBlocked('R02_FULL_SOURCE_OBJECT_INVALID')

        audit = r02_full_source_input.audit

        prepared = r02_full_source_input.prepared

        if (audit.get('approved_for_official_write') is not False

                or audit.get('period_start') != start.isoformat()

                or audit.get('period_end') != end.isoformat()

                or audit.get('grid_count') != len(grid_rows)

                or audit.get('prepared_grid_count') != len(grid_rows)

                or audit.get('mapped_eligible_rows') != len(prepared.eligible_rows)

                or audit.get('mapped_excluded_rows', -1) < 0

                or audit.get('unmapped_quarantined_rows', -1) < 0

                or audit.get('source_rows') !=

                   (audit['mapped_eligible_rows'] +

                    audit['mapped_excluded_rows'] +

                    audit['unmapped_quarantined_rows'])):

            raise InputBlocked('R02_SCORING_INPUT_CONTRACT_MISMATCH')

        scoring_reviewed_rows = list(prepared.eligible_rows)

    candidates,evidence=assemble_official_score(grid_rows=grid_rows,reviewed_rows=scoring_reviewed_rows,


        start=start,end=end,policy_document=document)


    # D-05 is not derivable from the score threshold or the D-06 confidence grade.


    # The current scorer explicitly leaves these five 78 fields unset.


    # Do not persist a misleading 'official' run until an approved D-05 rule


    # is implemented and every candidate carries an evaluated condition result.


    # D-05 explicitly permits UNKNOWN (NULL) when a normalized domain was


    # not observed. Validate consistency instead of rejecting every NULL.


    d05_rule = validate_d05_rule(document.get('d05_rule'))


    for candidate in candidates:


        verify_d05_persisted_conditions(candidate, d05_rule)


    result=run_official_pipeline(OfficialInputs(setting_version_id=setting_version_id,


        policy_evidence_dir=evidence_dir,build_id=build_id,start=start,end=end,


        gids=frozenset(r['ID_gid'] for r in grid_rows),reviewed_complaints=tuple(reviewed_rows),


        scored_candidates=candidates,evidence_by_gid=evidence,authorized_by=authorized_by,


        approval_reference=approval_reference, setting_references=references, existing_run_id=existing_run_id),explicit_db_write_approval=explicit_db_write_approval,


        read_only=read_only,connection_factory=connection_factory,r02_full_source_input=r02_full_source_input)


    return result


