"""F-03/F-04 display supplies. No arbitrary JSON approval via environment variables.

F03 A/B/C: no verified rule-by-rule rating is currently available, so supply none.
F04: published team-leader *work* contacts from traceable official org-chart PDFs.
These numbers must NOT be labeled 'team representative numbers'.
"""
from __future__ import annotations

from app.services.standards.f01_official_directory import OFFICIAL_TEAM_LEAD_DIRECTORY


def load_display_sources():
    # An absence of F03 ratings is a deliberate safe state, not an A grade.
    return {}, list(OFFICIAL_TEAM_LEAD_DIRECTORY), 'TEAM_LEAD_DIRECTORY_ONLY_GRADE_UNVERIFIED'
