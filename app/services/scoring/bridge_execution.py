"""Connect AI-01/C-08 inspection inventory to experimental nine-indicator execution.

Deliberately does not issue a scoring-ready complaint aggregate: review, period,
location and full source coverage contracts remain unapproved. Read-only.
"""
from __future__ import annotations

from .complaint_bridge import inspect_classified_source
from .execution import prepare


def preview_with_unverified_complaints(grid, source, config):
    """Audit the source and compute *base-only* evidence with final ranks blocked.

    `source` must be the exact classified-source snapshot whose IDs and schema
    match the AI-01 / C-08 output. Never use preview counts as official input.
    """
    if 'ID_gid' not in grid.columns:
        raise ValueError('BRIDGE_GRID_ID_MISSING')
    inspected = inspect_classified_source(source, grid['ID_gid'])
    # Explicitly omit complaint aggregates even if the caller supplied related
    # labels: review completeness, source coverage and official policies are
    # unknown. `prepare` must consequently leave final scores/ranks NULL.
    result = prepare(grid, config, source=source, complaints=None)
    if result['official_score_generated'] or any(
        row['score'] is not None or row['rank_no'] is not None for row in result['rows']
    ):
        raise AssertionError('BRIDGE_EXPERIMENTAL_FINAL_SCORE_LEAK')
    result['complaint_bridge'] = {
        'inventory': inspected.inventory,
        'preview_counts': inspected.preview.to_dict(orient='records'),
        'eligible_for_official': False,
        'meaning': 'PREVIEW_NOT_SCORE_INPUT',
    }
    return result
