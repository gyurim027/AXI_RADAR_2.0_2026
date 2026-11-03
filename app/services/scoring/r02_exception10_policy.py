"""Immutable, user-approved 2022–2025 R02 checkpoint exception rule.

Never changes source classifications. Fail closed if checkpoint, source identity,
exception membership, or partition digest differs from the approved evidence.
"""
from __future__ import annotations
from datetime import date
from hashlib import sha256
import json

POLICY_ID = 'R02_FAILED_CHECKPOINT10_EXPLICIT_QUARANTINE_APPROVED_20261103_V1'
REASON = 'R02_FAILED_CHECKPOINT_NO_CLASSIFICATION_HISTORY'
START, END = date(2022, 1, 1), date(2025, 12, 31)
CHECKPOINT_SHA = '9a96cdaadee0a273f1ac9f29a2ac8151473633ad9fe0fca9af702d801d8cda6b'
BASE_SOURCE_SHA = 'ed0942f7cf1e07570994b33c67fbe4bfd78395d4307ba45e3323dadb6efc21cf'
IDS_MANIFEST_SHA = '942d6e9fc5c09f9d4cb5831b32ba783606c1036829394d7115aade855c5495ba'
EXPECTED_COUNTS_SHA = 'e4f208935f2b866a1fd0dca155ed9d7d7c6a630549aa7272fe4947c93c660bde'

class DispositionBlocked(ValueError):
    pass

def _hash_pairs(ids):
    payload = json.dumps([(cid, REASON) for cid in sorted(ids)], sort_keys=True,
                         ensure_ascii=True, separators=(',', ':')).encode('utf-8')
    return sha256(payload).hexdigest()

def select_approved_exceptions(source, *, gids, checkpoint_failures, checkpoint_sha, source_sha, start, end):
    """Keep identifiers in memory; the emitted receipt contains only hashes and counts."""
    if (start, end) != (START, END):
        raise DispositionBlocked('EXCEPTION_POLICY_PERIOD_MISMATCH')
    if checkpoint_sha != CHECKPOINT_SHA or source_sha != BASE_SOURCE_SHA:
        raise DispositionBlocked('EXCEPTION_POLICY_BASELINE_CHANGED')
    fail = {}
    for item in checkpoint_failures:
        cid = str(item.get('cid') or '').strip()
        if not cid or cid in fail or item.get('status') not in ('error', 'mask_failed'):
            raise DispositionBlocked('EXCEPTION_CHECKPOINT_IDENTITY_INVALID')
        fail[cid] = item['status']
    if len(fail) != 76 or list(fail.values()).count('error') != 1 or list(fail.values()).count('mask_failed') != 75:
        raise DispositionBlocked('EXCEPTION_CHECKPOINT_POPULATION_CHANGED')
    from app.services.scoring.approved_inputs import classification_decision
    rows = {str(r['complaint_id']): r for r in source}
    if len(rows) != len(source):
        raise DispositionBlocked('EXCEPTION_SOURCE_DUPLICATE_ID')
    valid = {str(g) for g in gids}
    inside, already_excluded, selected = 0, 0, set()
    for cid in fail:
        row = rows.get(cid)
        if row is None:
            continue
        inside += 1
        d = classification_decision(row)
        typ = row.get('ped_type')
        typ_present = isinstance(typ, str) and bool(typ.strip())
        if row.get('gid') is None or str(row['gid']) not in valid or d is None or (d == 'Y' and not typ_present):
            already_excluded += 1
            continue
        selected.add(cid)
    if (76-inside, already_excluded, len(selected)) != (63, 3, 10):
        raise DispositionBlocked('EXCEPTION_CHECKPOINT_SPLIT_CHANGED')
    if _hash_pairs(selected) != IDS_MANIFEST_SHA:
        raise DispositionBlocked('EXCEPTION_10_IDENTITIES_CHANGED')
    return frozenset(selected)


def approved_exclusion_receipt():
    return {'exception_policy': POLICY_ID, 'exception_reason': REASON,
            'exception_count': 10, 'checkpoint_sha256': CHECKPOINT_SHA,
            'exception_manifest_sha256': IDS_MANIFEST_SHA,
            'source_baseline_sha256': BASE_SOURCE_SHA,
            'expected_eligible_counts_sha256': EXPECTED_COUNTS_SHA}
