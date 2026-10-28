"""Read-only bridge from actual AI-01/C-08 classifications to scoring aggregate.

Does NOT classify missing text, approve a policy, or write to shared DB.
Partial/unreviewed source cannot be exported as a verified official aggregate.
"""
from __future__ import annotations

from dataclasses import dataclass
import pandas as pd

LABELS = frozenset({'보행안전 관련', '비관련', '불명'})
REQUIRED = frozenset({'complaint_id', 'gid', 'relevance', 'class_confidence',
                      'coord_accuracy', 'dup_flag'})


@dataclass(frozen=True)
class BridgeResult:
    inventory: dict
    preview: pd.DataFrame
    eligible_for_official: bool = False


def inspect_classified_source(rows: pd.DataFrame, gids, *, accepted_location=('높음', '중간')) -> BridgeResult:
    """Produce a NON-OFFICIAL preview, never a verified scoring input.

    Unclassified and ambiguous rows remain visible as blockers, not fabricated
    zeros. Repeated and low-accuracy records remain excluded from the preview.
    An approved period/repeat/quality policy and independent source coverage
    verification are still needed before a scoring-ready aggregate is issued.
    """
    missing = sorted(REQUIRED - set(rows.columns))
    if missing:
        raise ValueError('BRIDGE_MISSING_COLUMNS:' + ','.join(missing))
    if rows.complaint_id.isna().any() or rows.complaint_id.astype(str).str.strip().eq('').any() or rows.complaint_id.duplicated().any():
        raise ValueError('BRIDGE_INVALID_COMPLAINT_IDS')
    grid = pd.Series(list(gids), dtype='object')
    if grid.isna().any() or grid.duplicated().any():
        raise ValueError('BRIDGE_INVALID_GRID_POPULATION')
    labels = rows.relevance.dropna().astype(str).str.strip()
    if not set(labels).issubset(LABELS):
        raise ValueError('BRIDGE_UNKNOWN_CLASSIFICATION_VOCABULARY')
    conf = pd.to_numeric(rows.class_confidence, errors='coerce')
    invalid_conf = rows.class_confidence.notna() & (~conf.between(0, 1))
    if invalid_conf.any():
        raise ValueError('BRIDGE_INVALID_CONFIDENCE')
    pending = rows.relevance.isna() | rows.relevance.eq('불명') | conf.isna()
    related = rows.relevance.eq('보행안전 관련') & ~pending
    assigned = rows.gid.isin(set(grid.tolist()))
    bad_grid = rows.gid.notna() & ~assigned
    if bad_grid.any():
        raise ValueError('BRIDGE_UNKNOWN_GRID_REFERENCE')
    duplicate_flag = rows.dup_flag.notna() & ~rows.dup_flag.astype(str).str.strip().isin(('', '0', 'N', 'n', 'False', 'false', '아니오'))
    valid_location = rows.coord_accuracy.isin(accepted_location)
    candidates = related & assigned & valid_location & ~duplicate_flag
    counts = rows.loc[candidates].groupby('gid', dropna=False).size()
    preview = pd.DataFrame({'gid': grid, 'preview_related_count': grid.map(counts).fillna(0).astype(int)})
    inventory = {
        'source_rows': int(len(rows)),
        'pending_or_unknown': int(pending.sum()),
        'related_labeled': int(related.sum()),
        'unassigned_grid': int(rows.gid.isna().sum()),
        'related_excluded_low_or_unknown_location': int((related & assigned & ~valid_location).sum()),
        'related_excluded_flagged_duplicate': int((related & assigned & duplicate_flag).sum()),
        'preview_candidate_rows': int(candidates.sum()),
        'preview_only': True,
        'official_blockers': ['CLASSIFICATION_REVIEW_NOT_ESTABLISHED', 'SOURCE_COVERAGE_NOT_VERIFIED',
                              'TIME_WINDOW_POLICY_PENDING', 'DEDUP_POLICY_PENDING',
                              'LOCATION_POLICY_PENDING', 'AGGREGATE_METADATA_NOT_APPROVED'],
    }
    if pending.any():
        inventory['official_blockers'].append('SOURCE_CLASSIFICATION_PENDING')
    return BridgeResult(inventory=inventory, preview=preview)
