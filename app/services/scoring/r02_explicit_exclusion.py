"""R-02 explicit exclusion policy: preserve unresolved, never infer N.

Pure pre-aggregation partition only. No DB writes, no silent bypass of official
pipeline. Caller must verify full source coverage, provenance, and approval.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from app.services.scoring.approved_inputs import classification_decision, InputBlocked

POLICY_ID = 'R02_UNRESOLVED_EXCLUSION_TEAM_SELECTED_20261101_V1'
POLICY_STATUS = 'TEAM_SELECTED_NOT_DB62_REGISTERED'
REQUIRED = frozenset({'complaint_id', 'received_date', 'gid', 'relevance', 'class_method', 'ped_type'})

@dataclass(frozen=True)
class Partition:
    eligible: tuple[dict, ...]
    excluded: tuple[dict, ...]
    counts: dict[str,int]
    digest: str


def partition_explicitly(rows, valid_gids, *, explicit_policy: bool = False) -> Partition:
    if explicit_policy is not True:
        raise InputBlocked('R02_EXCLUSION_POLICY_EXPLICIT_SELECTION_REQUIRED')
    valid_gids = {str(v) for v in valid_gids}
    if not valid_gids:
        raise InputBlocked('R02_GRID_POPULATION_EMPTY')
    eligible, excluded, seen = [], [], set()
    counts = Counter()
    for row in rows:
        if not isinstance(row, dict) or not REQUIRED <= row.keys():
            raise InputBlocked('R02_SOURCE_FIELDS_INCOMPLETE')
        cid = str(row['complaint_id'] or '').strip()
        if not cid or cid in seen:
            raise InputBlocked('DUPLICATE_OR_EMPTY_COMPLAINT_ID')
        seen.add(cid)
        gid = None if row['gid'] is None else str(row['gid'])
        if gid not in valid_gids:
            raise InputBlocked('R02_UNMAPPED_REQUIRES_SEPARATE_POLICY')
        else:
            decision = classification_decision(row)
            if decision is None:
                reason = 'UNRESOLVED_CLASSIFICATION'
            elif decision == 'Y' and (not isinstance(row['ped_type'], str) or not row['ped_type'].strip()):
                reason = 'RELATED_TYPE_MISSING'
            else:
                # Retain Y/N *as classified*, do not rewrite unresolved to N.
                eligible.append(dict(row))
                counts['eligible_related' if decision == 'Y' else 'eligible_nonrelated'] += 1
                continue
        counts[reason] += 1
        excluded.append({'complaint_id':cid, 'gid':gid, 'reason':reason})
    counts['source'] = len(seen)
    counts['excluded'] = len(excluded)
    counts['eligible'] = len(eligible)
    if counts['source'] != counts['eligible'] + counts['excluded']:
        raise InputBlocked('R02_EXCLUSION_ACCOUNTING_MISMATCH')
    # Digest only stable case keys and reasons. Do not write PII manifests in audit output.
    digest = sha256(json.dumps(sorted((x['complaint_id'],x['reason']) for x in excluded),
                               ensure_ascii=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    return Partition(tuple(eligible), tuple(excluded), dict(counts), digest)
