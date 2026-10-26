"""Compare all three complaint-integration modes on the same authoritative inputs.

Read-only analysis: not an official run, not a policy approval, never writes 77/78.
The per-mode score is calculated by the *existing* operational scorer, not a new formula.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from app.services.scoring.operational_scoring import assemble_official_score

MODES = ('independent', 'inside_hazard', 'bonus')


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str,
                             separators=(',', ':')).encode('utf-8')).hexdigest()


def compare_all_modes(*, grid_rows: list[dict], reviewed_rows: list[dict],
                      start, end, policy_document: dict, top_n: int = 35) -> dict:
    """Compute A/B/C on identical data, retaining complete per-gid evidence.

    Uses the specified complaint strength, normalization, missing and weighting
    from the supplied policy document. No mode is auto-elected as official.
    """
    if not isinstance(top_n, int) or top_n < 1:
        raise ValueError('INVALID_TOP_N')
    if not isinstance(policy_document, dict):
        raise ValueError('POLICY_DOCUMENT_REQUIRED')
    records: dict[str, tuple[dict, ...]] = {}
    evidence: dict[str, dict] = {}
    summaries: dict[str, dict] = {}
    expected = None
    for mode in MODES:
        doc = deepcopy(policy_document)
        doc['complaint_mode'] = mode
        candidates, details = assemble_official_score(
            grid_rows=grid_rows, reviewed_rows=reviewed_rows,
            start=start, end=end, policy_document=doc)
        gids = {row['gid'] for row in candidates}
        if expected is None:
            expected = gids
        elif gids != expected:
            raise ValueError('MODE_GRID_POPULATION_CHANGED')
        if len(gids) != len(candidates) or set(details) != gids:
            raise ValueError('MODE_EVIDENCE_INCOMPLETE')
        ordered = sorted(candidates, key=lambda r:(r['rank_no'], -r['official_score'],r['gid']))
        records[mode] = candidates
        evidence[mode] = details
        summaries[mode] = {'grid_count':len(candidates), 'top_gids':[r['gid'] for r in ordered[:top_n]],
                           'min_score':min(r['official_score'] for r in candidates),
                           'max_score':max(r['official_score'] for r in candidates),
                           'selected_count':sum(r['selected_yn']=='Y' for r in candidates)}
    overlap={}
    for i, left in enumerate(MODES):
        for right in MODES[i+1:]:
            overlap[f'{left}__{right}'] = len(set(summaries[left]['top_gids']) & set(summaries[right]['top_gids']))
    scores = {mode:{row['gid']:row for row in rows} for mode, rows in records.items()}
    comparison = []
    for gid in sorted(expected or ()):
        base = {'gid':gid}
        for mode in MODES:
            row = scores[mode][gid]
            base[mode+'_score'] = row['official_score']
            base[mode+'_rank'] = row['rank_no']
            base[mode+'_selected'] = row['selected_yn']
        comparison.append(base)
    return {'status':'THREE_MODE_COMPARISON_NOT_AN_OFFICIAL_RUN',
            'input_sha256':_digest({'gids':sorted(expected or ()), 'reviewed':reviewed_rows,
                                   'policy':policy_document, 'start':str(start), 'end':str(end)}),
            'modes':list(MODES), 'summary':summaries, 'top_n_overlap':overlap,
            'comparison':comparison, 'evidence_by_mode':evidence}
