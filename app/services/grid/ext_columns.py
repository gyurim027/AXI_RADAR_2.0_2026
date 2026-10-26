"""05 grid_feature의 EXT_ 21열을 DB 표에서 다시 센다 (B-02 격자 점 세기의 은경 쪽 열, 세은 재계산용, 초안 v0.1).

예전에는 은경 PC의 추출테이블 엑셀(T 시트)로 셌다(build_ext.py + hotspot_fix.py + v17_data.py).
그 엑셀의 값은 이미 DB 원천·판정 표에 gid와 같이 들어가 있어서, 여기서는 DB 표만 읽어 같은 규칙으로 센다.
규칙은 05 칸 설명(COMMENT)과 같다. 지금 05 값과의 대조 결과는 docs/grid/ext_columns.md.

    from app.services.grid.ext_columns import compute
    rows = compute()          # {gid: {"ext_signal_controller_cnt": 3, ...}} — 2,406칸 모두 (없으면 0)
"""
from __future__ import annotations

from collections import Counter, defaultdict

from app.core import db

COLUMNS = [
    "ext_g_no", "ext_ped_hotspot_point_cnt", "ext_ped_hotspot_repeat_sum", "ext_signal_controller_cnt",
    "ext_hump_crosswalk_cnt", "ext_ped_priority_candidate_cnt_2022", "ext_bike_road_endpoint_cnt",
    "ext_parking_enforce_cnt", "ext_crosswalk_short_signal_cnt", "ext_crosswalk_signal_unknown_cnt",
    "ext_crosswalk_lux_under6_cnt", "ext_crosswalk_guide_check_cnt", "ext_floor_signal_cnt",
    "ext_floor_signal_missing_crosswalk_cnt", "ext_camera_speed_cnt", "ext_camera_signal_cnt", "ext_camera_parking_cnt",
    "ext_camera_other_cnt", "ext_zone_drawing_zone_cnt", "ext_survey_scope_obstacle", "ext_survey_scope_zone_2022",
]

# 칸 → (읽는 표, 규칙) — 문서·대조표에 그대로 씀
RULES = {
    "ext_g_no": ("01 grid_cell.g_no", "은경 격자 번호 그대로"),
    "ext_ped_hotspot_point_cnt": ("39 src_ped_hotspot_5y", "지점 이름(spot_name)+칸 기준 서로 다른 지점 수"),
    "ext_ped_hotspot_repeat_sum": ("39 src_ped_hotspot_5y", "칸에 있는 지점마다 그 지점 첫 행의 repeat_cnt_21_25를 더함"),
    "ext_signal_controller_cnt": ("41 src_signal_controller", "gid가 있는 행 수"),
    "ext_hump_crosswalk_cnt": ("42 src_hump_crosswalk", "gid가 있는 행 수"),
    "ext_ped_priority_candidate_cnt_2022": ("(이어 씀)", "2022 후보지 61곳 — 예전 T11 격자 집계 값. DB gid로 세면 29칸이 다름"),
    "ext_bike_road_endpoint_cnt": ("52 src_bike_road", "start_grid_no·end_grid_no를 격자 번호로 바꿔 끝점 수"),
    "ext_parking_enforce_cnt": ("45 src_parking_enforce_place", "gid별 enforce_cnt 합"),
    "ext_crosswalk_short_signal_cnt": ("07 assess_crosswalk", "sig_check_result가 '부족'으로 시작"),
    "ext_crosswalk_signal_unknown_cnt": ("07 assess_crosswalk", "sig_check_result가 '판단 불가' 또는 '현시마다 다름'으로 시작"),
    "ext_crosswalk_lux_under6_cnt": ("07 assess_crosswalk", "lux_check_result가 '최소'로 시작"),
    "ext_crosswalk_guide_check_cnt": ("07 assess_crosswalk", "guide_check_needed가 있고 '8차로'가 없음"),
    "ext_floor_signal_cnt": ("50 src_floor_signal", "gid가 있는 행 수"),
    "ext_floor_signal_missing_crosswalk_cnt": ("50 src_floor_signal", "result가 '100m 안 표준'으로 시작"),
    "ext_camera_speed_cnt": ("51 src_enforce_camera_all", "enforce_class = 속도"),
    "ext_camera_signal_cnt": ("51 src_enforce_camera_all", "enforce_class = 신호"),
    "ext_camera_parking_cnt": ("51 src_enforce_camera_all", "enforce_class = 불법주정차"),
    "ext_camera_other_cnt": ("51 src_enforce_camera_all", "enforce_class = 기타"),
    "ext_zone_drawing_zone_cnt": ("(이어 씀)", "2025 도면 11곳 — 도면 중심점 칸 기준이라 10 assess_zone의 gid(보호구역 칸)로 세면 5칸이 다름"),
    "ext_survey_scope_obstacle": ("(이어 씀)", "2022 적치물 조사 범위 — 보행자전용도로 선이 지나는 칸이라 도형이 필요, DB 점만으로는 272칸 중 163~195칸만 나옴"),
    "ext_survey_scope_zone_2022": ("(이어 씀)", "2022 보호구역 조사 범위 — DB로 다시 세면 410칸 중 373칸, 나머지는 예전 T11 조사 칸 값"),
}


def _q(sql: str, args=()):
    return db.read_only(sql, args)


# DB 표만으로 똑같이 다시 셀 수 없는 칸 → 지금 05 값을 그대로 이어 씀.
# 모두 한 번 조사한 자료(2022 조사 범위·2022 후보지·2025 도면)라 반기 갱신 때 바뀌지 않는다.
CARRY = ("ext_ped_priority_candidate_cnt_2022", "ext_zone_drawing_zone_cnt", "ext_survey_scope_obstacle",
         "ext_survey_scope_zone_2022")


def compute(keep_from_current: tuple[str, ...] = CARRY) -> dict[str, dict]:
    """2,406칸 × EXT_ 21열. keep_from_current 칸은 지금 05 값을 그대로 가져온다(원천이 DB에 없음)."""
    cells = _q("SELECT gid, g_no FROM grid_cell")
    g2gid = {c["g_no"]: c["gid"] for c in cells}
    out = {c["gid"]: {k: 0 for k in COLUMNS} for c in cells}
    for c in cells:
        out[c["gid"]]["ext_g_no"] = c["g_no"]

    def add(col, counter):
        for gid, v in counter.items():
            if gid in out:
                out[gid][col] = v

    # 39 보행자 다발지: 지점 이름+칸
    hs = _q("SELECT row_id, spot_name, gid, repeat_cnt_21_25 FROM src_ped_hotspot_5y ORDER BY row_id")
    first = {}
    for r in hs:
        first.setdefault(r["spot_name"], r["repeat_cnt_21_25"] or 0)
    pairs = {(r["spot_name"], r["gid"]) for r in hs if r["gid"]}
    add("ext_ped_hotspot_point_cnt", Counter(g for _, g in pairs))
    rep = Counter()
    for name, g in pairs:
        rep[g] += int(first.get(name) or 0)
    add("ext_ped_hotspot_repeat_sum", rep)

    for col, table in (("ext_signal_controller_cnt", "src_signal_controller"), ("ext_hump_crosswalk_cnt", "src_hump_crosswalk"),
                       ("ext_ped_priority_candidate_cnt_2022", "src_ped_priority_candidate"),
                       ("ext_floor_signal_cnt", "src_floor_signal")):
        add(col, {r["gid"]: int(r["n"]) for r in _q(f"SELECT gid, COUNT(*) n FROM {table} WHERE gid IS NOT NULL GROUP BY gid")})

    ends = Counter()
    for r in _q("SELECT start_grid_no, end_grid_no FROM src_bike_road"):
        for g in (r["start_grid_no"], r["end_grid_no"]):
            if g in g2gid:
                ends[g2gid[g]] += 1
    add("ext_bike_road_endpoint_cnt", ends)

    add("ext_parking_enforce_cnt", {r["gid"]: int(r["n"] or 0) for r in _q(
        "SELECT gid, SUM(enforce_cnt) n FROM src_parking_enforce_place WHERE gid IS NOT NULL GROUP BY gid")})

    cw = _q("SELECT gid, sig_check_result s, lux_check_result l, guide_check_needed g FROM assess_crosswalk WHERE gid IS NOT NULL")
    add("ext_crosswalk_short_signal_cnt", Counter(r["gid"] for r in cw if str(r["s"] or "").startswith("부족")))
    add("ext_crosswalk_signal_unknown_cnt", Counter(r["gid"] for r in cw if str(r["s"] or "").startswith(("판단 불가", "현시마다 다름"))))
    add("ext_crosswalk_lux_under6_cnt", Counter(r["gid"] for r in cw if str(r["l"] or "").startswith("최소")))
    add("ext_crosswalk_guide_check_cnt", Counter(r["gid"] for r in cw if r["g"] and "8차로" not in str(r["g"])))

    add("ext_floor_signal_missing_crosswalk_cnt", {r["gid"]: int(r["n"]) for r in _q(
        "SELECT gid, COUNT(*) n FROM src_floor_signal WHERE gid IS NOT NULL AND result LIKE '100m 안 표준%%' GROUP BY gid")})

    cams = _q("SELECT gid, enforce_class k, COUNT(*) n FROM src_enforce_camera_all WHERE gid IS NOT NULL GROUP BY gid, enforce_class")
    for col, k in (("ext_camera_speed_cnt", "속도"), ("ext_camera_signal_cnt", "신호"), ("ext_camera_parking_cnt", "불법주정차"),
                   ("ext_camera_other_cnt", "기타")):
        add(col, {r["gid"]: int(r["n"]) for r in cams if r["k"] == k})

    add("ext_zone_drawing_zone_cnt", {r["gid"]: int(r["n"]) for r in _q(
        "SELECT gid, COUNT(*) n FROM assess_zone WHERE gid IS NOT NULL AND dwg2025_kind IS NOT NULL GROUP BY gid")})

    red = {r["gid"] for r in _q("SELECT DISTINCT gid FROM src_red_surface WHERE gid IS NOT NULL")}
    sign = {r["gid"] for r in _q("SELECT DISTINCT gid FROM src_zone_sign WHERE gid IS NOT NULL")}
    mit = {r["ID_gid"] for r in _q("SELECT ID_gid FROM grid_feature WHERE COALESCE(mit_fence_cnt,0) > 0 "
                                   "OR COALESCE(mit_enforce_camera_cnt,0) > 0 OR COALESCE(mit_yellow_carpet_cnt,0) > 0")}
    for gid in out:
        out[gid]["ext_survey_scope_zone_2022"] = "Y" if gid in red | sign | mit else "N"

    if keep_from_current:
        # 05를 새로 만들면 이 칸이 비므로 DB가 아니라 저장해 둔 파일(SQL v2.1 값)에서 가져온다
        import csv
        from pathlib import Path
        f = Path(__file__).resolve().parents[3] / "data" / "grid" / "ext_carry_05_v2_1.csv"
        with open(f, encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                if r["ID_gid"] in out:
                    for c in keep_from_current:
                        v = r[c]
                        out[r["ID_gid"]][c] = int(v) if v.lstrip("-").isdigit() else v
    return out


def compare_with_current(new: dict[str, dict]) -> dict:
    """지금 05 값과 칸마다 비교 → {칸: {"same": n, "diff": n, "examples": [...]}}"""
    cur = {r["ID_gid"]: r for r in _q("SELECT ID_gid, " + ", ".join(f"`{c}`" for c in COLUMNS) + " FROM grid_feature")}
    res = {}
    for c in COLUMNS:
        same = diff = 0
        ex = []
        for gid, row in new.items():
            a, b = _norm(cur.get(gid, {}).get(c)), _norm(row.get(c))
            if a == b:
                same += 1
            else:
                diff += 1
                if len(ex) < 5:
                    ex.append({"gid": gid, "now": a, "new": b})
        res[c] = {"same": same, "diff": diff, "examples": ex}
    return res


def _norm(v):
    if v is None:
        return 0
    try:
        f = float(v)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return str(v)


# ── 06 grid_feature_ng (수치지형도 파생) ─────────────────
NG_COLUMNS = [
    "extng_sidewalk_status", "extng_sidewalk_area_m2", "extng_area_weighted_avg_width_m", "extng_width_under2_cnt",
    "extng_width_under15_cnt", "extng_slope_over_1_12_cnt", "extng_sidewalk_lux_under_p6_cnt",
    "extng_fence_cond4_sidewalk_cnt", "extng_fence_cond3_no_record_cnt", "extng_crosswalk_no_refuge_4lane_cnt",
    "extng_intersection_sight_check_cnt",
]
# 보도 면적·폭 5칸은 보도 도형과 격자의 겹친 면적이라 수치지형도 도형이 있어야 함 → 이어 씀 (도면이 2025년 판 그대로면 안 바뀜)
NG_CARRY = NG_COLUMNS[:5]
NG_RULES = {
    "extng_slope_over_1_12_cnt": ("08 assess_sidewalk", "slope_over_1_12 = Y 이고 slope_usable = 참고 가능"),
    "extng_sidewalk_lux_under_p6_cnt": ("08 assess_sidewalk", "lux_check_result가 'P6'으로 시작"),
    "extng_fence_cond4_sidewalk_cnt": ("08 assess_sidewalk", "fence_result = 울타리 필요 조건 많음(4개 이상)"),
    "extng_fence_cond3_no_record_cnt": ("08 assess_sidewalk", "fence_cond_cnt ≥ 3 이고 fence_cnt_15m_2022 = 0"),
    "extng_crosswalk_no_refuge_4lane_cnt": ("07 assess_crosswalk", "ng_refuge_result에 '없음'·'차로'가 있고 '3'으로 시작하지 않음"),
    "extng_intersection_sight_check_cnt": ("09 assess_intersection", "result = 시야 확인 우선"),
}


def compute_ng(keep_from_current: tuple[str, ...] = tuple(NG_CARRY)) -> dict[str, dict]:
    cells = _q("SELECT gid, g_no FROM grid_cell")
    g2gid = {c["g_no"]: c["gid"] for c in cells}
    out = {c["gid"]: {k: 0 for k in NG_COLUMNS} for c in cells}
    sw = _q("SELECT gid, grid_no_250m g, slope_over_1_12 s, slope_usable u, lux_check_result l, fence_result f, "
            "fence_cond_cnt c, fence_cnt_15m_2022 k FROM assess_sidewalk")
    def cell(r):
        return r["gid"] or g2gid.get(r["g"])
    cnt = defaultdict(Counter)
    for r in sw:
        g = cell(r)
        if not g:
            continue
        if r["s"] == "Y" and r["u"] == "참고 가능":
            cnt["extng_slope_over_1_12_cnt"][g] += 1
        if str(r["l"] or "").startswith("P6"):
            cnt["extng_sidewalk_lux_under_p6_cnt"][g] += 1
        if r["f"] == "울타리 필요 조건 많음(4개 이상)":
            cnt["extng_fence_cond4_sidewalk_cnt"][g] += 1
        if (r["c"] or 0) >= 3 and (r["k"] or 0) == 0:
            cnt["extng_fence_cond3_no_record_cnt"][g] += 1
    for r in _q("SELECT gid, ng_refuge_result v FROM assess_crosswalk WHERE gid IS NOT NULL"):
        v = str(r["v"] or "")
        if "없음" in v and "차로" in v and not v.startswith("3"):
            cnt["extng_crosswalk_no_refuge_4lane_cnt"][r["gid"]] += 1
    for r in _q("SELECT gid, COUNT(*) n FROM assess_intersection WHERE gid IS NOT NULL AND result = '시야 확인 우선' GROUP BY gid"):
        cnt["extng_intersection_sight_check_cnt"][r["gid"]] = int(r["n"])
    for col, c in cnt.items():
        for g, v in c.items():
            if g in out:
                out[g][col] = v
    if keep_from_current:
        for r in _q("SELECT ID_gid, " + ", ".join(f"`{c}`" for c in keep_from_current) + " FROM grid_feature_ng"):
            if r["ID_gid"] in out:
                for c in keep_from_current:
                    out[r["ID_gid"]][c] = r[c]
    return out


def compare_ng_with_current(new: dict[str, dict]) -> dict:
    cur = {r["ID_gid"]: r for r in _q("SELECT ID_gid, " + ", ".join(f"`{c}`" for c in NG_COLUMNS) + " FROM grid_feature_ng")}
    res = {}
    for c in NG_COLUMNS:
        same = diff = 0
        ex = []
        for gid, row in new.items():
            a, b = _norm(cur.get(gid, {}).get(c)), _norm(row.get(c))
            if a == b:
                same += 1
            else:
                diff += 1
                if len(ex) < 5:
                    ex.append({"gid": gid, "now": a, "new": b})
        res[c] = {"same": same, "diff": diff, "examples": ex}
    return res
