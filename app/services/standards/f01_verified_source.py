
"""F-01 approved read-only original-row loader (two verified source schemas).

Refuses unknown source types, missing GID, ambiguous identifiers, and source
records without matching GID. Never infers an original row from grid totals.
"""
from __future__ import annotations
from app.core import db

# Identifier names are fixed in code; runtime input binds values only.
SOURCE_SQL = {
    "src_complaint": ("SELECT complaint_id, gid, report_type_raw, gu, lat, lon, coord_method, coord_accuracy FROM src_complaint "
                      "WHERE complaint_id = %s AND gid = %s LIMIT 2", "complaint_id"),
    "src_road_hazard": ("SELECT row_id, gid, `type`, gu, lat, lon, coord_method, coord_accuracy FROM src_road_hazard "
                        "WHERE row_id = %s AND gid = %s LIMIT 2", "row_id"),
}


def load_verified_f01_row(*, table: str, gid: str, source_id: str) -> dict:
    if table not in SOURCE_SQL:
        raise ValueError("SOURCE_SCHEMA_NOT_VERIFIED")
    if not isinstance(gid, str) or not gid.strip() or not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("GID_OR_ID_REQUIRED")
    query, key = SOURCE_SQL[table]
    rows = db.read_only(query, (source_id, gid))
    if len(rows) != 1:
        raise ValueError("SOURCE_ROW_MISSING_OR_NOT_UNIQUE")
    row = rows[0]
    if str(row.get(key, '')) != source_id or str(row.get('gid', '')) != gid:
        raise ValueError("SOURCE_ROW_IDENTITY_MISMATCH")
    return row
