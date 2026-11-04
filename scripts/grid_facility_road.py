"""F-02 시설-도로 연결 - 시설 좌표마다 가장 가까운 표준 링크를 찾아 도로 정보를 붙인다 (대환님 F-01용).

1차 대상 8종 (대환님 10/23): 04 crosswalk · 22 streetlight · 30 speed_bump · 32 fence · 33 road_sign ·
                             35 traffic_light · 42 hump_crosswalk · 50 floor_signal
판정 3단계 (대환님 10/26 의견) - 자동으로 담당 부서를 정하지 않는다 (부서 배정은 F-01)
  1) --max(기본 30m) 이내   기본 연결 기준. 아래 경우는 '확인 필요'로 남긴다
       연결
       확인 필요: 다른 도로가 비슷한 거리   관할표 이름이 다른 링크가 가장 가까운 링크보다 --gap(기본 10m) 안쪽으로 더 있음 (30m 안에서만 찾음)
       확인 필요: 같은 등급의 다른 도로가 비슷한 거리   관할표 이름은 같은데 도로 이름·노선이 다른 링크가 --same-gap(기본 --gap) 안쪽으로 더 있음.
                  같은 도로가 이어진 링크, 이름·노선이 비어 있어 알 수 없는 링크는 세지 않음 (대환님 10/27)
       확인 필요: 가장 가까운 도로가 고속도로   고속국도·도시고속도로 (보행 불가 등급)
       확인 필요: 시설 자료의 도로 종류와 다름  33·35의 road_class와 링크 도로 종류가 다름
  2) --max 초과 ~ --far(기본 100m) 이내   거리 기준 초과·추가 확인 필요   (가장 가까운 링크 정보는 참고로 남김)
  3) --far 이내에 링크 없음   링크 미확인   (관할·담당 부서는 임의로 판단하지 않음)
  '우선 확인 대상'(Y): 위 '같은 등급의 다른 도로가 비슷한 거리'로 확인 필요가 된 시설 중, 시설 이름·주소에 가장 가까운 링크의 도로 이름이 들어 있는 곳.
  연결 가능성이 높은 사례라서 먼저 보라는 표시일 뿐 판정은 '확인 필요' 그대로다 (대환님 10/27: 자동 확정은 보류).
시설과 링크 사이의 거리(m)는 항상 남긴다. 대안 링크(관할표 이름이 다른 가장 가까운 링크)는 '다른 도로'·'다른 도로 LINK_ID'·'다른 도로 거리_m'.
시설 관리기관(mgmt_org_name)은 참고로 옮겨 적기만 한다 - 도로 관리기관과 시설 관리기관은 별개라 확정에 쓰지 않음.

사용법 (저장소 루트)
  uv run python -m scripts.grid_facility_road [--csv <v2 CSV 폴더>] [--max 30] [--far 100] [--gap 10] [--same-gap 10]
결과 (out/grid/)
  f02_facility_road.csv          시설 1개 = 1줄
  f02_facility_road_summary.csv  표 × 판정(연결·확인 필요·거리 기준 초과·링크 미확인) 시설 수
  f02_facility_road_reasons.csv  '확인 필요' 사유별 건수 (한 시설에 사유가 여럿이면 각각 셈 - 시설 수와 다름)
"""
import argparse
import re
import sys

import geopandas as gpd
import numpy as np
import pandas as pd

from app.services.grid import build_grid_table as B, config as C, source as S

ap = argparse.ArgumentParser()
ap.add_argument("--csv"); ap.add_argument("--max", type=float, default=30.0); ap.add_argument("--gap", type=float, default=10.0)
ap.add_argument("--same-gap", type=float, default=None, help="'같은 등급의 다른 도로가 비슷한 거리' 기준(m). 비우면 --gap과 같음")
ap.add_argument("--far", type=float, default=100.0, help="링크를 찾는 최대 거리 (--max 초과~--far는 '거리 기준 초과')")
a = ap.parse_args()
if a.csv:
    S.use_csv(a.csv)
if a.far < a.max:
    sys.exit("--far는 --max보다 같거나 커야 합니다.")
SAME_GAP = a.gap if a.same_gap is None else a.same_gap

RANK = {"101": "고속국도", "102": "도시고속도로", "103": "일반국도", "104": "특별·광역시도",
        "105": "국가지원지방도", "106": "지방도", "107": "시·군도", "108": "기타"}
JUR = {"101": "고속국도", "102": "도시고속도로", "103": "국도", "104": "특별·광역시도",
       "105": "국가지원지방도", "106": "지방도", "107": "시도", "108": "기타"}       # 88 jurisdiction_dept 조건 이름
NO_PREFIX = {"103": "국도", "105": "국지도", "106": "지방도"}
NO_WALK = {"101", "102"}
TARGETS = {  # 표: (이름 칸 후보, 시설 자료의 도로 종류 칸)
    "crosswalk": (["road_name", "lot_address"], None),
    "src_streetlight": (["streetlight_name", "road_address", "lot_address"], None),
    "src_speed_bump": (["road_name", "road_address"], None),
    "src_fence": (["target_facility_name", "road_name", "road_address"], None),
    "src_road_sign": (["route_name", "road_address"], "road_class"),
    "src_traffic_light": (["route_name", "road_address"], "road_class"),
    "src_hump_crosswalk": (["install_place", "install_road_address"], None),
    "src_floor_signal": (["facility_location_name"], None),
}


def road_kind(text: str) -> str | None:
    """시설 자료의 road_class 글자를 관할표 이름으로 (예: '시도' · '일반국도' · '지방도')."""
    t = str(text or "")
    for k, v in (("고속", "고속국도"), ("국가지원", "국가지원지방도"), ("지방도", "지방도"), ("국도", "국도"),
                 ("특별", "특별·광역시도"), ("광역", "특별·광역시도"), ("시도", "시도"), ("군도", "시도"), ("구도", "시도")):
        if k in t:
            return v
    return None


try:
    sys.stdout.reconfigure(errors="replace")      # 파이프(| Select-String)로 이어 받아도 cp949로 못 쓰는 글자 때문에 멈추지 않게
except Exception:
    pass

B.BASE = C.RAW_DIR
lp = B.first(["성남", "링크"], (".shp",))
if lp is None:
    sys.exit(f"성남_링크.shp를 못 찾았어요 - .env의 RADAR_GRID_RAW_DIR({C.RAW_DIR})를 확인하세요.")
L = gpd.read_file(lp, encoding="cp949").to_crs(B.CRS_M).reset_index(drop=True)
L["rank"] = L["ROAD_RANK"].astype(str).str[:3]
L["도로 종류"] = L["rank"].map(RANK).fillna("기타")
L["관할표 이름"] = L["rank"].map(JUR).fillna("기타")
no = pd.to_numeric(L["ROAD_NO"].astype(str).str.extract(r"(\d+)")[0], errors="coerce")
L["노선"] = [f"{NO_PREFIX[r]}{int(n)}호선" if r in NO_PREFIX and pd.notna(n) else None for r, n in zip(L["rank"], no)]
_nm = L["ROAD_NAME"].fillna("").astype(str).str.strip()
nm = _nm.mask(_nm.str.fullmatch(r"[\W_]*") | _nm.isin(["없음", "미상", "무명", "NULL", "null", "None", "nan"]), "").to_numpy()   # 도로 이름 ('-' 같은 이름 없음 표시·빈 글자 = 모름)
rt = L["노선"].fillna("").astype(str).to_numpy()                          # 노선 (빈 글자 = 모름)


def other_road(i: int, j: int) -> bool:
    """두 링크(i, j)가 서로 다른 도로인가. 이름이나 노선이 양쪽 다 있고 다를 때만 True (같은 도로가 이어진 링크·한쪽이 비어 알 수 없으면 False)."""
    return bool((nm[i] and nm[j] and nm[i] != nm[j]) or (rt[i] and rt[j] and rt[i] != rt[j]))


sidx = L.sindex

rows = []
for t, (name_cols, rc) in TARGETS.items():
    head = S.columns(t)
    key = head[0]
    use = [c for c in [key, "lat", "lon", "gid", "mgmt_org_name", rc, *name_cols] if c and c in head]
    d = S.read(t, usecols=list(dict.fromkeys(use)))
    d = d.assign(lat=pd.to_numeric(d["lat"], errors="coerce"), lon=pd.to_numeric(d["lon"], errors="coerce"))
    d = d[d["lat"].notna() & d["lon"].notna()].reset_index(drop=True)
    P = gpd.GeoSeries(gpd.points_from_xy(d["lon"], d["lat"]), crs=4326).to_crs(B.CRS_M)
    # buffer는 원이 아니라 다각형이라 경계(반지름 -0.12m쯤) 근처 링크를 놓칠 수 있다 → 1m 더 넓게 찾고, 아래에서 실제 거리로 거른다
    pi, li = sidx.query(P.buffer(a.far + 1), predicate="intersects")
    dist = P.iloc[pi].reset_index(drop=True).distance(L.geometry.iloc[li].reset_index(drop=True)).to_numpy()
    cand = pd.DataFrame({"p": pi, "l": li, "dist": dist})
    cand = cand[cand["dist"] <= a.far].sort_values(["p", "dist", "l"])
    first = cand.drop_duplicates("p").set_index("p")
    groups = cand.groupby("p").indices                     # 시설별 후보 줄 (거리순)
    cl, cd = cand["l"].to_numpy(), cand["dist"].to_numpy()
    jur = L["관할표 이름"].to_numpy()
    name = d[[c for c in name_cols if c in d.columns]].astype(str).replace("nan", "").agg(lambda r: next((x for x in r if x), ""), axis=1)
    for i in range(len(d)):
        rec = {"표": t, "행 키": f"{key}={d.at[i, key]}", "gid": d.at[i, "gid"] if "gid" in d else None,
               "시설 이름·주소": name.iat[i], "시설 관리기관(참고)": d.at[i, "mgmt_org_name"] if "mgmt_org_name" in d else None,
               "시설 자료 도로 종류": d.at[i, rc] if rc and rc in d else None}
        if i not in first.index:
            rows.append({**rec, "판정": "링크 미확인"}); continue                      # --far 이내에 링크 없음
        f = first.loc[i]; l1 = L.iloc[int(f["l"])]; d1 = float(f["dist"])
        rec.update({"LINK_ID": l1["LINK_ID"], "도로 종류": l1["도로 종류"], "관할표 이름": l1["관할표 이름"], "노선": l1["노선"],
                    "도로 이름": l1["ROAD_NAME"], "거리_m": round(d1, 2)})
        idx = groups[i]
        diff_i = [j for j in idx if jur[cl[j]] != l1["관할표 이름"]]               # 관할표 이름이 다른 링크 (거리순)
        if diff_i:
            j = diff_i[0]; l2 = L.iloc[int(cl[j])]
            rec.update({"다른 도로": f"{l2['관할표 이름']} {l2['ROAD_NAME']}", "다른 도로 LINK_ID": l2["LINK_ID"],
                        "다른 도로 거리_m": round(float(cd[j]), 2)})
        n1 = int(f["l"])
        same_i = [j for j in idx if int(cl[j]) != n1 and jur[cl[j]] == l1["관할표 이름"] and other_road(n1, int(cl[j]))]   # 같은 등급·다른 도로 (거리순)
        if same_i:
            j = same_i[0]; l3 = L.iloc[int(cl[j])]
            rec.update({"같은 등급 다른 도로": f"{l3['관할표 이름']} {l3['ROAD_NAME']}", "같은 등급 다른 도로 LINK_ID": l3["LINK_ID"],
                        "같은 등급 다른 도로 거리_m": round(float(cd[j]), 2)})
        if d1 > a.max:
            rows.append({**rec, "판정": "거리 기준 초과·추가 확인 필요"}); continue     # --max 초과 ~ --far 이내
        reasons = []
        if l1["rank"] in NO_WALK:
            reasons.append("가장 가까운 도로가 고속도로")
        if diff_i and cd[diff_i[0]] <= a.max and cd[diff_i[0]] - d1 <= a.gap:         # 대안 링크도 --max 안에서만 (10/23 결과와 같게)
            reasons.append("다른 도로가 비슷한 거리")
        if same_i and cd[same_i[0]] <= a.max and cd[same_i[0]] - d1 <= SAME_GAP:      # 같은 등급의 다른 도로 (대환님 10/27 추가)
            reasons.append("같은 등급의 다른 도로가 비슷한 거리")
        rk = road_kind(rec["시설 자료 도로 종류"])
        if rk and rk != l1["관할표 이름"]:
            reasons.append("시설 자료의 도로 종류와 다름")
        if "같은 등급의 다른 도로가 비슷한 거리" in reasons and nm[n1] and nm[n1] in str(rec["시설 이름·주소"]):
            rec["우선 확인 대상"] = "Y"                                               # 판정은 그대로 '확인 필요' (자동 확정 안 함)
        rows.append({**rec, "판정": "연결" if not reasons else "확인 필요: " + " · ".join(reasons)})
    print(f"  {t}: {len(d):,}곳")

R = pd.DataFrame(rows)
cols = ["표", "행 키", "gid", "시설 이름·주소", "판정", "우선 확인 대상", "LINK_ID", "도로 종류", "관할표 이름", "노선", "도로 이름", "거리_m",
        "다른 도로", "다른 도로 LINK_ID", "다른 도로 거리_m", "같은 등급 다른 도로", "같은 등급 다른 도로 LINK_ID", "같은 등급 다른 도로 거리_m", "시설 자료 도로 종류", "시설 관리기관(참고)"]
R = R.reindex(columns=cols)
R.to_csv(C.OUT_DIR / "f02_facility_road.csv", index=False, encoding="utf-8-sig")
TIERS = ["연결", "확인 필요", "거리 기준 초과", "링크 미확인"]
R["판정(묶음)"] = R["판정"].map(lambda v: "연결" if v == "연결" else "확인 필요" if v.startswith("확인 필요")
                                 else "거리 기준 초과" if v.startswith("거리 기준 초과") else "링크 미확인")
Sm = R.pivot_table(index="표", columns="판정(묶음)", values="행 키", aggfunc="count", fill_value=0).reindex(columns=TIERS, fill_value=0)
Sm["합계"] = Sm.sum(axis=1)
Sm.loc["전체"] = Sm.sum()
Sm.to_csv(C.OUT_DIR / "f02_facility_road_summary.csv", encoding="utf-8-sig")
pd.set_option("display.width", 200)
print("\n시설 수 (표 × 판정):\n" + Sm.to_string())
need = R[R["판정(묶음)"] == "확인 필요"]
rc = need["판정"].str.replace("확인 필요: ", "", regex=False).str.split(" · ").explode().value_counts()
rc.rename_axis("사유").rename("사유 건수").to_csv(C.OUT_DIR / "f02_facility_road_reasons.csv", encoding="utf-8-sig")
print(f"\n확인 필요: 시설 {len(need):,}곳 · 사유 {int(rc.sum()):,}건 (한 시설에 사유가 여럿이면 사유마다 셈)")
print(rc.rename_axis("사유").to_string())
pri = R[R["우선 확인 대상"] == "Y"]
print(f"\n우선 확인 대상: {len(pri):,}곳 (확인 필요 중 '같은 등급의 다른 도로가 비슷한 거리'이면서 시설 이름·주소에 가장 가까운 링크의 도로 이름이 들어 있는 곳) - 판정은 '확인 필요' 그대로")
print(f"\n저장: {C.OUT_DIR / 'f02_facility_road.csv'} ({len(R):,}곳), f02_facility_road_summary.csv, f02_facility_road_reasons.csv")
print("* 담당 부서는 정하지 않음 (F-01). 시설 관리기관은 참고로만.")
