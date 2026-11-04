"""Pre-aggregation bridge for the team-selected R-02 exclusion policy.

Maintains complete source accounting, excludes unresolved (not relabelled N),
blocks unmapped, enforces period, and uses the unchanged official aggregator.
This alone does NOT authorize writes or replace the official pipeline's
approved-input and provenance gates.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from app.services.scoring.approved_inputs import aggregate_reviewed_complaints, InputBlocked
from app.services.scoring.r02_explicit_exclusion import partition_explicitly, POLICY_ID

@dataclass(frozen=True)
class PreparedR02:
    eligible_rows: tuple[dict, ...]
    counts_by_gid: tuple[dict, ...]
    audit: dict

def prepare_r02_official_input(rows, *, gids, start, end,
                               explicit_exclusion_policy=False, exception_ids=frozenset()):
    if not isinstance(start,date) or not isinstance(end,date) or start>end:
        raise InputBlocked('R02_INVALID_PERIOD')
    if explicit_exclusion_policy is not True:
        raise InputBlocked('R02_EXCLUSION_POLICY_EXPLICIT_SELECTION_REQUIRED')
    gids={str(g) for g in gids}
    rows=list(rows)
    # Fail closed if any supplied row falls outside the approved period.
    # Do not silently reduce the reported source population.
    for row in rows:
        dt=row.get('received_date') if isinstance(row,dict) else None
        if isinstance(dt,str):
            try:dt=date.fromisoformat(dt[:10])
            except ValueError as exc:raise InputBlocked('R02_INVALID_RECEIVED_DATE') from exc
        if not isinstance(dt,date) or not start<=dt<=end:
            raise InputBlocked('R02_SOURCE_PERIOD_MISMATCH')
    p=partition_explicitly(rows,gids,explicit_policy=True)
    exception_ids = {str(x) for x in exception_ids}
    eligible_ids = {str(r['complaint_id']) for r in p.eligible}
    if not exception_ids <= eligible_ids:
        raise InputBlocked('R02_EXCEPTIONS_NOT_ELIGIBLE_IN_THIS_INPUT')
    active = tuple(r for r in p.eligible if str(r['complaint_id']) not in exception_ids)
    counts=aggregate_reviewed_complaints(list(active),start=start,end=end,gids=gids)
    if len(counts)!=len(gids) or any(r['classification_status']!='COMPLETE' for r in counts):
        raise InputBlocked('R02_ELIGIBLE_AGGREGATION_INCOMPLETE')
    if len(active) + p.counts['excluded'] + len(exception_ids) != p.counts['source']:
        raise InputBlocked('R02_SOURCE_ACCOUNTING_MISMATCH')
    # Manifest hash contains no individual records or complaint text.
    # Its originating snapshot, immutable provenance and authorization must
    # be persisted and verified in the actual official write path later.
    audit={
        'policy_id':POLICY_ID,
        'status':'TEAM_SELECTED_NOT_DB62_REGISTERED',
        'period_start':start.isoformat(), 'period_end':end.isoformat(),
        'source_rows':p.counts['source'],
        'eligible_rows':len(active),
        'excluded_rows':p.counts['excluded']+len(exception_ids),
        'eligible_related':sum(r['relevant_count'] for r in counts),
        'eligible_nonrelated':sum(r['irrelevant_count'] for r in counts),
        'excluded_reasons':{k:v for k,v in sorted(p.counts.items())
                            if k in ('UNRESOLVED_CLASSIFICATION','RELATED_TYPE_MISSING')},
        'excluded_manifest_sha256':p.digest,
        'grid_count':len(gids),
        'approved_for_official_write':False,
    }
    if exception_ids:
        from app.services.scoring.r02_exception10_policy import REASON
        audit['excluded_reasons'][REASON] = len(exception_ids)
        audit['exception_excluded_count'] = len(exception_ids)
        digest = sha256(json.dumps(sorted([(r['complaint_id'], r['reason']) for r in p.excluded] +
                                          [(cid, REASON) for cid in exception_ids]),
                                          ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()
        audit['excluded_manifest_sha256'] = digest
    return PreparedR02(active,tuple(counts),audit)
