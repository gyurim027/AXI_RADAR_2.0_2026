"""Join failed checkpoint identities to the existing source audit, without scoring.

Private IDs and classifications stay in memory. Aggregate hashes identify this
comparison; they neither approve policy nor authorize an official database write.
"""
from collections import Counter
from datetime import date, datetime
from hashlib import sha256
import json

from app.services.scoring.approved_inputs import InputBlocked, classification_decision
from app.services.scoring.source_audit_lineage import verify_source_audit


def _canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode()


def _id(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise InputBlocked('R02_LINK_INVALID_ID')
    result = str(value).strip()
    if not result:
        raise InputBlocked('R02_LINK_INVALID_ID')
    return result


def reconcile_exceptions(exceptions, source_rows, *, gids, audit_raw,
                         expected_audit_sha256, checkpoint_sha256, start, end,
                         expected_statuses=None):
    """Compare the *same* exclusions to the prior audit and then join exceptions.

    No reclassification, aggregate_reviewed_complaints, score calculation, or DB
    operation occurs. Caller must supply rows from one consistent read snapshot.
    """
    verified = verify_source_audit(audit_raw, expected_sha256=expected_audit_sha256,
                                  start=start, end=end)
    audit_doc = json.loads(audit_raw.decode('utf-8-sig'))
    audit = audit_doc.get('audit', audit_doc)
    if (not isinstance(checkpoint_sha256, str) or len(checkpoint_sha256) != 64
            or any(c not in '0123456789abcdef' for c in checkpoint_sha256)):
        raise InputBlocked('R02_LINK_INVALID_CHECKPOINT_HASH')
    expected_statuses = ({'mask_failed': 75, 'error': 1}
                         if expected_statuses is None else expected_statuses)
    failed = {}
    for item in exceptions:
        cid = _id(item.get('cid'))
        if cid in failed or item.get('status') not in ('mask_failed', 'error'):
            raise InputBlocked('R02_LINK_CHECKPOINT_IDENTITIES_INVALID')
        failed[cid] = item['status']
    if dict(Counter(failed.values())) != expected_statuses or not failed:
        raise InputBlocked('R02_LINK_CHECKPOINT_POPULATION_MISMATCH')
    valid = {str(g) for g in gids}
    if len(valid) != verified.grid_count:
        raise InputBlocked('R02_LINK_GRID_POPULATION_MISMATCH')
    seen = set()
    counts = Counter()
    excluded_keys, unmapped_keys = [], []
    excluded_reasons, unmapped_reasons, buckets = Counter(), Counter(), Counter()
    matched = set()
    for row in source_rows:
        if not isinstance(row, dict) or not {
                'complaint_id', 'gid', 'received_date', 'relevance',
                'class_method', 'ped_type'} <= row.keys():
            raise InputBlocked('R02_LINK_SOURCE_FIELDS_MISSING')
        cid = _id(row['complaint_id'])
        if cid in seen:
            raise InputBlocked('R02_LINK_DUPLICATE_SOURCE_ID')
        seen.add(cid)
        dt = row['received_date']
        if isinstance(dt, datetime): dt = dt.date()
        if isinstance(dt, str):
            try: dt = date.fromisoformat(dt[:10])
            except ValueError: raise InputBlocked('R02_LINK_INVALID_DATE') from None
        if not isinstance(dt, date) or not start <= dt <= end:
            raise InputBlocked('R02_LINK_SOURCE_PERIOD_MISMATCH')
        gid = row['gid']
        decision = classification_decision(row)
        has_type = isinstance(row['ped_type'], str) and bool(row['ped_type'].strip())
        if gid is not None and str(gid) in valid:
            counts['mapped_rows'] += 1
            if decision is None: reason = 'UNRESOLVED_CLASSIFICATION'
            elif decision == 'Y' and not has_type: reason = 'RELATED_TYPE_MISSING'
            else: reason = None
            if reason:
                excluded_keys.append((cid, reason)); excluded_reasons[reason] += 1
                counts['mapped_excluded_rows'] += 1; bucket = 'mapped_excluded'
            else:
                counts['mapped_eligible_rows'] += 1
                counts['mapped_eligible_related' if decision == 'Y' else 'mapped_eligible_nonrelated'] += 1
                bucket = 'eligible'
        else:
            if gid is not None and str(gid).strip():
                raise InputBlocked('R02_LINK_UNKNOWN_NONNULL_GID')
            reason = ('RELATED_WITH_TYPE' if has_type else 'RELATED_TYPE_MISSING') if decision == 'Y' else ('NONRELATED' if decision == 'N' else 'UNRESOLVED')
            unmapped_keys.append((cid, reason)); unmapped_reasons[reason] += 1
            counts['unmapped_quarantined_rows'] += 1; bucket = 'unmapped_quarantined'
        if cid in failed:
            matched.add(cid); buckets[bucket] += 1
            if row['relevance'] is not None or row['ped_type'] is not None:
                buckets['classification_changed'] += 1
    counts['source_rows'] = len(seen)
    for key in ('source_rows', 'mapped_rows', 'mapped_eligible_rows',
                'mapped_excluded_rows', 'unmapped_quarantined_rows',
                'mapped_eligible_related', 'mapped_eligible_nonrelated'):
        if counts[key] != audit.get(key):
            raise InputBlocked('R02_LINK_AUDIT_COUNTS_CHANGED')
    # The existing partition contract hashes sorted (ID, reason) pairs as arrays.
    mapped_hash = sha256(json.dumps(sorted(excluded_keys), ensure_ascii=True,
                                   separators=(',', ':')).encode()).hexdigest()
    unmapped_hash = sha256(json.dumps(sorted(unmapped_keys), ensure_ascii=True,
                                     separators=(',', ':')).encode()).hexdigest()
    if (mapped_hash != audit['mapped_excluded_sha256']
            or unmapped_hash != audit['unmapped_quarantined_sha256']
            or dict(excluded_reasons) != audit['mapped_exclusion_reasons']
            or dict(unmapped_reasons) != audit['unmapped_quarantine_reasons']):
        raise InputBlocked('R02_LINK_AUDIT_MANIFEST_CHANGED')
    buckets['missing'] = len(failed.keys() - matched)
    if buckets['missing'] or buckets['eligible'] or buckets['classification_changed']:
        raise InputBlocked('R02_LINK_EXCEPTION_NOT_SAFELY_QUARANTINED')
    report = {
        'schema_version': 'R02_EXCEPTION_LINK_V1', 'status': 'PASS',
        'checkpoint_sha256': checkpoint_sha256,
        'checkpoint_exception_statuses': dict(Counter(failed.values())),
        'exception_count': len(failed), 'matched_exception_count': len(matched),
        'exception_buckets': {k: buckets[k] for k in (
            'mapped_excluded', 'unmapped_quarantined', 'eligible',
            'missing', 'classification_changed')},
        'source_audit_sha256': verified.audit_sha256,
        'mapped_excluded_sha256': mapped_hash,
        'unmapped_quarantined_sha256': unmapped_hash,
        'source_counts': {k: counts[k] for k in sorted(counts)},
        'identifiers_exported': False, 'raw_rows_saved': False,
        'classification_rerun': 0, 'scoring_executed': False,
        'official_write_authorized': False,
    }
    report['report_sha256'] = sha256(_canonical(report)).hexdigest()
    return report
