"""Full-population R02 audit policy. No relabels, remapping, or database writes."""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from app.services.scoring.approved_inputs import classification_decision, InputBlocked
from app.services.scoring.r02_official_input_bridge import prepare_r02_official_input, PreparedR02
from app.services.scoring.r02_explicit_exclusion import POLICY_ID as MAPPED_EXCLUSION_POLICY_ID
UNMAPPED_POLICY_ID = 'R02_UNMAPPED_QUARANTINE_TEAM_APPROVED_20261101_V1'

@dataclass(frozen=True)
class FullSourceR02:
    prepared: PreparedR02
    audit: dict

def prepare_full_source_r02(rows, *, gids, start, end, mapped_exclusion_policy=False,
                            unmapped_quarantine_policy=False, exception_ids=frozenset(), exception_receipt=None):
    if mapped_exclusion_policy is not True or unmapped_quarantine_policy is not True:
        raise InputBlocked('R02_BOTH_POLICIES_EXPLICITLY_REQUIRED')
    if not isinstance(start,date) or not isinstance(end,date) or start>end:
        raise InputBlocked('R02_INVALID_PERIOD')
    valid={str(g) for g in gids}
    if not valid:raise InputBlocked('R02_EMPTY_GRID_SET')
    mapped=[]; unmapped=[]; seen=set(); quarantined=Counter(); keys=[]
    for row in rows:
        if not isinstance(row,dict) or not {'complaint_id','gid','received_date','relevance','class_method','ped_type'} <= row.keys():
            raise InputBlocked('R02_SOURCE_FIELDS_INCOMPLETE')
        cid=str(row['complaint_id'] or '').strip()
        if not cid or cid in seen:raise InputBlocked('R02_DUPLICATE_OR_EMPTY_COMPLAINT_ID')
        seen.add(cid)
        dt=row['received_date']
        if isinstance(dt,str):
            try:dt=date.fromisoformat(dt[:10])
            except ValueError as exc:raise InputBlocked('R02_DATE_INVALID') from exc
        if not isinstance(dt,date) or not start<=dt<=end:
            raise InputBlocked('R02_SOURCE_PERIOD_MISMATCH')
        gid=row['gid']
        if gid is not None and str(gid) in valid:
            mapped.append(row)
            continue
        # This approval covers only missing grid IDs, not alien/nonexistent IDs.
        if gid is not None and str(gid).strip():
            raise InputBlocked('R02_UNKNOWN_NONNULL_GID_NOT_AUTHORIZED')
        decision=classification_decision(row)
        if decision=='Y':
            typ=row.get('ped_type')
            reason='RELATED_WITH_TYPE' if isinstance(typ,str) and typ.strip() else 'RELATED_TYPE_MISSING'
        elif decision=='N':reason='NONRELATED'
        else:reason='UNRESOLVED'
        quarantined[reason]+=1
        # Sensitive identifiers remain only in memory for deterministic digest.
        keys.append((cid,reason))
        unmapped.append(row)
    prepared=prepare_r02_official_input(mapped,gids=valid,start=start,end=end,
                                         explicit_exclusion_policy=True,exception_ids=exception_ids)
    unmapped_digest=sha256(json.dumps(sorted(keys),ensure_ascii=True,separators=(',',':')).encode()).hexdigest()
    audit={
      'policy_mapped':MAPPED_EXCLUSION_POLICY_ID,
      'policy_unmapped':UNMAPPED_POLICY_ID,
      'period_start':start.isoformat(),'period_end':end.isoformat(),
      'source_rows':len(seen),'mapped_rows':len(mapped),'unmapped_quarantined_rows':len(unmapped),
      'mapped_eligible_rows':prepared.audit['eligible_rows'],
      'mapped_excluded_rows':prepared.audit['excluded_rows'],
      'mapped_eligible_related':prepared.audit['eligible_related'],
      'mapped_eligible_nonrelated':prepared.audit['eligible_nonrelated'],
      'mapped_exclusion_reasons':prepared.audit['excluded_reasons'],
      'unmapped_quarantine_reasons':dict(sorted(quarantined.items())),
      'mapped_excluded_sha256':prepared.audit['excluded_manifest_sha256'],
      'unmapped_quarantined_sha256':unmapped_digest,
      'grid_count':len(valid),'prepared_grid_count':len(prepared.counts_by_gid),
      'classification_modified':False,'grid_assignment_modified':False,
      'approved_for_official_write':False,
      'limitations':('Unmapped related complaints contribute no grid score; '
                     'quarantine is not a nonrelated classification; '
                     'immutable source provenance and signed durable audit pending.')
    }
    if exception_ids:
        from app.services.scoring.r02_exception10_policy import approved_exclusion_receipt
        if exception_receipt != approved_exclusion_receipt() or len(exception_ids) != 10:
            raise InputBlocked('R02_EXCEPTION_POLICY_RECEIPT_INVALID')
        audit['approved_exception_disposition'] = dict(exception_receipt)
        audit['mapped_exclusion_reasons'] = dict(prepared.audit['excluded_reasons'])
    if (audit['mapped_eligible_rows']+audit['mapped_excluded_rows']+audit['unmapped_quarantined_rows'] != audit['source_rows']):
        raise InputBlocked('R02_FULL_SOURCE_ACCOUNTING_MISMATCH')
    if audit['prepared_grid_count']!=audit['grid_count']:
        raise InputBlocked('R02_GRID_COVERAGE_MISMATCH')
    # Audit digest is SHA256 of canonical public aggregate fields; source snapshot
    # itself must be separately verified and persisted before official writes.
    audit['audit_sha256']=sha256(json.dumps(audit,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()
    return FullSourceR02(prepared,audit)
