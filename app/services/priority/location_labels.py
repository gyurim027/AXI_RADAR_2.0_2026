"""Read-only grid-linked reference addresses and named places for candidate display.

Both fields describe source records linked to the candidate's grid (gid).  They are
NOT reverse-geocoded center-point addresses, nearest-place calculations or a
proof that the hazard occurred at the named location. Missing values stay None.
"""
from __future__ import annotations

import logging

from collections.abc import Callable, Sequence
from typing import Any

# Each candidate source has an FK/index on gid in RADAR v2.4. Do not use
# complaint.location_text: it is unstructured and may contain personal data.
# Column names are from v2.4 SQL and CSV, not guessed at request time.
_SOURCES: tuple[tuple[str, str, str, str, str], ...] = (
    # table, id, address expression, landmark expression, provenance
    ("zone", "zone_id", "t01_road_address", "facility_name", "보호구역 시설"),
    ("src_child_facility", "src_id", "road_address", "place_name", "어린이집·유치원"),
    ("src_crosswalk", "src_id", "COALESCE(NULLIF(TRIM(road_address), ''), NULLIF(TRIM(lot_address), ''))", "NULL", "횡단보도"),
    ("src_safety_cctv", "src_id", "COALESCE(NULLIF(TRIM(road_address), ''), NULLIF(TRIM(lot_address), ''))", "NULL", "안전 CCTV"),
    ("src_streetlight", "src_id", "COALESCE(NULLIF(TRIM(road_address), ''), NULLIF(TRIM(lot_address), ''))", "NULL", "보안등"),
    ("src_bus_stop_list", "row_id", "NULL", "stop_name", "버스정류소"),
)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _sql(gid_count: int) -> str:
    if gid_count < 1:
        raise ValueError("gid_count must be positive")
    placeholders = ", ".join(["%s"] * gid_count)
    selects = []
    for index, (table, row_key, address_expr, landmark_expr, _) in enumerate(_SOURCES):
        selects.append(
            f"SELECT gid, {address_expr} AS ref_address, {landmark_expr} AS ref_landmark, "
            f"{index} AS source_order, CAST({row_key} AS CHAR) AS ref_key "
            f"FROM {table} WHERE gid IN ({placeholders})"
            + (" AND useYn = 'Y'" if table == "zone" else "")
        )
    return (
        "SELECT gid, ref_address, ref_landmark, source_order, ref_key FROM ("
        + " UNION ALL ".join(selects)
        + ") AS refs WHERE ref_address IS NOT NULL OR ref_landmark IS NOT NULL "
        "ORDER BY gid, source_order, ref_key"
    )


def location_labels_for_gids(
    gids: Sequence[str], read_only: Callable[[str, Sequence[Any]], list[dict]]
) -> dict[str, dict[str, Any]]:
    """Fetch labels in one read-only query, not one query per candidate.

    Keep separate provenance because address/landmark may come from different
    facilities in the same grid. No synthetic address or name is manufactured.
    """
    unique = list(dict.fromkeys(x for x in gids if isinstance(x, str) and x))
    if not unique:
        return {}
    # Bounded by priority endpoint limit=3000; chunk to limit SQL packet/params.
    result: dict[str, dict[str, Any]] = {}
    for start in range(0, len(unique), 250):
        chunk = unique[start:start + 250]
        args = tuple(chunk) * len(_SOURCES)
        try:
            rows = read_only(_sql(len(chunk)), args)
        except Exception:
            # Address/landmark are optional enrichments. A query failure must
            # not turn an otherwise valid candidate list into HTTP 500.
            logging.getLogger(__name__).exception(
                "Optional candidate location lookup failed; returning null labels"
            )
            return {}
        allowed = set(chunk)
        for row in rows:
            gid = row.get("gid")
            if gid not in allowed:
                continue
            try:
                source_no = int(row["source_order"])
                source = _SOURCES[source_no][4]
            except (KeyError, ValueError, TypeError, IndexError):
                continue
            item = result.setdefault(gid, {
                "address": None, "landmark": None,
                "addressSource": None, "landmarkSource": None,
            })
            if item["address"] is None:
                value = _clean(row.get("ref_address"))
                if value is not None:
                    item["address"] = value
                    item["addressSource"] = source
            if item["landmark"] is None:
                value = _clean(row.get("ref_landmark"))
                if value is not None:
                    item["landmark"] = value
                    item["landmarkSource"] = source
    return result


def attach_location(row: dict[str, Any], labels: dict[str, dict[str, Any]]) -> None:
    entry = labels.get(row.get("gid"), {})
    for field in ("address", "landmark", "addressSource", "landmarkSource"):
        row[field] = entry.get(field)
