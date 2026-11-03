"""C-07 full-source (2021 through latest 2026 monthly update) grid contract.

This is the *raw* C-07 contract, not a human-reviewed relevance count.
Rows with unknown relevance remain unknown. All 05 GIDs are retained.
No mutations of DB or reviewer statuses are performed.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime
from hashlib import sha256
from app.services.scoring.approved_inputs import classification_decision
import json

class ComplaintContractError(ValueError):
    pass


def _day(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError) as exc:
        raise ComplaintContractError('INVALID_RECEIVED_DATE') from exc


def build_contract(source_rows, grid_gids, *, earliest=date(2021, 1, 1), through=None):
    """Return all-month raw counts, per-source/month matrix and explicit coverage.

    `through=None` uses latest observed receipt date, NOT current clock date.
    Completeness is measured against all dated source records in scope, not only
    gid-bearing records. Candidate classifications don't count as approvals.
    """
    gids = tuple(str(x) for x in grid_gids)
    if len(gids) != len(set(gids)) or not gids:
        raise ComplaintContractError('INVALID_GRID_POPULATION')
    if not isinstance(earliest, date):
        raise ComplaintContractError('INVALID_PERIOD_START')
    records = list(source_rows)
    if not records:
        raise ComplaintContractError('NO_SOURCE_COMPLAINTS')
    seen = set()
    normalized = []
    for record in records:
        rid = record.get('complaint_id')
        if rid is None or str(rid).strip() == '' or str(rid) in seen:
            raise ComplaintContractError('DUPLICATE_OR_NULL_COMPLAINT_ID')
        seen.add(str(rid))
        day = _day(record.get('received_date'))
        normalized.append((day, record))
    last = max(day for day, _ in normalized) if through is None else through
    if not isinstance(last, date) or last < earliest:
        raise ComplaintContractError('INVALID_PERIOD_END')
    mapped = set(gids)
    by_gid = {gid: {'gid': gid, 'complaint_cnt': 0, 'complaint_cnt_excl_low': 0,
                    'reviewed_relevant_count': 0, 'reviewed_relevant_excl_low': 0,
                    'reviewed_count': 0, 'unreviewed_count': 0,
                    'repeat_relevant_count': 0, 'relevant_count': 0, 'count_excl_low': 0,
                    'unresolved_count': 0, 'classification_status': 'COMPLETE'} for gid in gids}
    monthly = defaultdict(lambda: {'total': 0, 'mapped': 0, 'unmapped': 0, 'reviewed': 0, 'unreviewed': 0, 'classified': 0, 'unresolved': 0})
    scoped = []
    for day, record in normalized:
        if day < earliest or day > last:
            continue
        month = day.strftime('%Y-%m')
        source = str(record.get('source_type') or 'UNKNOWN')
        bucket = monthly[(month, source)]
        bucket['total'] += 1
        gid = str(record.get('gid')).strip() if record.get('gid') is not None else ''
        matched = gid in mapped
        bucket['mapped' if matched else 'unmapped'] += 1
        rel = str(record.get('relevance') or '').strip()
        status = str(record.get('review_status') or '').strip().upper()
        # Only an independent reviewer confirmation is evidence for scored related/irrelevant.
        confirmed = status == 'CONFIRMED' and rel in {'Y', 'N', '보행안전 관련', '비관련'}
        decision = classification_decision(record)
        bucket['classified' if decision is not None else 'unresolved'] += 1
        bucket['reviewed' if confirmed else 'unreviewed'] += 1
        scoped.append((day, str(record['complaint_id']), gid, decision, confirmed, record))
        if not matched:
            continue
        target = by_gid[gid]
        target['complaint_cnt'] += 1
        low = str(record.get('coord_accuracy') or '').strip() == '낮음'
        if not low:
            target['complaint_cnt_excl_low'] += 1
        if decision == 'Y' and record.get('ped_type'):
            target['relevant_count'] += 1
            if not low:
                target['count_excl_low'] += 1
        if confirmed:
            target['reviewed_count'] += 1
            if decision == 'Y':
                target['reviewed_relevant_count'] += 1
                if not low:
                    target['reviewed_relevant_excl_low'] += 1
        else:
            target['unreviewed_count'] += 1
        if decision is None or (decision == 'Y' and not record.get('ped_type')):
            target['unresolved_count'] += 1
            target['classification_status'] = 'INCOMPLETE'
    seen_type_dates = defaultdict(set)
    for day, cid, gid, rel, confirmed, record in sorted(scoped, key=lambda x:(x[0],x[1])):
        if gid not in mapped or rel != 'Y':
            continue
        kind = str(record.get('ped_type') or '').strip()
        if not kind:
            # Do not infer a repeat without a validated type.
            continue
        key = gid, kind
        if seen_type_dates[key] and day not in seen_type_dates[key]:
            by_gid[gid]['repeat_relevant_count'] += 1
        seen_type_dates[key].add(day)
    months = [{'month': month, 'source_type': source, **dict(count)}
              for (month, source), count in sorted(monthly.items())]
    manifest = {'period_start': str(earliest), 'period_end': str(last),
                'source_row_count': len(records), 'scoped_row_count': len(scoped),
                'gid_count': len(gids), 'monthly_source': months,
                'classification_policy': 'CONFIRMED_OVERRIDE_OR_ACCEPTED_AI_RULE',
                'repeat_rule': 'distinct_received_dates_per_gid_type',
                'raw_counts_not_official_relevance': True}
    manifest['sha256'] = sha256(json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                                         separators=(',', ':')).encode('utf-8')).hexdigest()
    return {'manifest': manifest, 'grids': [by_gid[g] for g in sorted(by_gid)]}
