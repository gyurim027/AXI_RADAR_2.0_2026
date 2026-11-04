"""F-02 도로 종류 판정 — 격자·링크마다 어떤 종류의 도로인지 판정해 F-01(담당 부서 연결, 대환)에 넘긴다.

원본: 성남_링크.shp (국토교통부 표준노드링크 2026-09-14, B-03과 같은 파일)
F-02는 '도로 종류'까지만 정한다. 어느 부서가 맡는지는 F-01이 이 값(종류·차로 수·도로 이름)으로 정한다.

ROAD_RANK (표준노드링크 도로 등급)
  101 고속국도 · 102 도시고속도로 · 103 일반국도 · 104 특별·광역시도
  105 국가지원지방도 · 106 지방도 · 107 시·군도 · 108 기타
관할표 이름: 88 jurisdiction_dept 조건에 쓰는 이름 (107 → '시도', 103 → '국도' 등)
노선: 국도·국지도·지방도는 '국도3호선'·'국지도57호선'처럼 (88의 '국도3호선·국지도57·23호선' 조건용)
ROAD_TYPE: 000 일반도로 · 001 고가차도 · 002 지하차도 · 003 교량 · 004 터널

사용법 (저장소 루트에서, uv run python -m scripts.<이 파일 이름>)
  python f02_road_type.py
결과
  out/f02_link_road_type.csv   링크별: LINK_ID·도로 종류·도로 형태·도로 이름·번호·차로 수·구·행정동·길이·지나는 gid
  out/f02_grid_road_type.csv   격자별: 주 도로 종류(칸 안 길이 최대)·종류별 길이·최대 차로 수·주요 도로 이름
"""
import sys
import pandas as pd
import geopandas as gpd
from app.services.grid import config as C, source as S
if "--csv" in sys.argv:                          # DB 대신 v2 CSV 폴더 읽기
    S.use_csv(sys.argv[sys.argv.index("--csv") + 1])
from app.services.grid import build_grid_table as B

RANK = {"101": "고속국도", "102": "도시고속도로", "103": "일반국도", "104": "특별·광역시도",
        "105": "국가지원지방도", "106": "지방도", "107": "시·군도", "108": "기타"}
TYPE = {"000": "일반도로", "001": "고가차도", "002": "지하차도", "003": "교량", "004": "터널"}
# 88 jurisdiction_dept의 조건 이름 (예: '시도', '국가지원지방도·지방도', '국도3호선·국지도57·23호선')
JUR_NAME = {"101": "고속국도", "102": "도시고속도로", "103": "국도", "104": "특별·광역시도",
            "105": "국가지원지방도", "106": "지방도", "107": "시도", "108": "기타"}
NO_PREFIX = {"103": "국도", "105": "국지도", "106": "지방도"}      # 노선 번호가 있는 도로
NO_WALK = {"101", "102"}                       # 보행자가 다닐 수 없는 도로 (B-03 보행 분석에서도 제외)

B.BASE = C.RAW_DIR
cells = B.load_grid()                           # cid·gid·geometry (EPSG:5179)
lp = B.first(["성남", "링크"], (".shp",))
links = gpd.read_file(lp, encoding="cp949").to_crs(B.CRS_M)
links["rank"] = links["ROAD_RANK"].astype(str).str[:3]
links["도로 종류"] = links["rank"].map(RANK).fillna("기타")
links["도로 형태"] = links["ROAD_TYPE"].astype(str).str.zfill(3).map(TYPE).fillna("기타")
links["보행 가능"] = (~links["rank"].isin(NO_WALK)).map({True: "Y", False: "N"})
links["관할표 이름"] = links["rank"].map(JUR_NAME).fillna("기타")
no = pd.to_numeric(links["ROAD_NO"].astype(str).str.extract(r"(\d+)")[0], errors="coerce")
links["노선"] = [f"{NO_PREFIX[r]}{int(n)}호선" if r in NO_PREFIX and pd.notna(n) else None for r, n in zip(links["rank"], no)]
links["LANES"] = pd.to_numeric(links["LANES"], errors="coerce")

ov = gpd.overlay(links[["LINK_ID", "rank", "도로 종류", "관할표 이름", "노선", "도로 형태", "보행 가능", "ROAD_NAME", "ROAD_NO", "LANES", "geometry"]],
                 cells[["gid", "geometry"]], how="intersection", keep_geom_type=True)
ov["칸 안 길이_m"] = ov.geometry.length.round(1)

# 링크별
gids = ov.groupby("LINK_ID")["gid"].apply(lambda s: ";".join(sorted(set(s))))
L = links.drop(columns="geometry").assign(지나는_gid=lambda d: d["LINK_ID"].map(gids))
L = L[["LINK_ID", "rank", "도로 종류", "관할표 이름", "노선", "도로 형태", "보행 가능", "ROAD_NAME", "ROAD_NO", "LANES", "MAX_SPD", "구", "행정동", "길이_m", "지나는_gid"]]
L = L.rename(columns={"rank": "ROAD_RANK", "ROAD_NAME": "도로 이름", "ROAD_NO": "도로 번호", "LANES": "차로 수", "MAX_SPD": "제한속도"})
L.to_csv(C.OUT_DIR / "f02_link_road_type.csv", index=False, encoding="utf-8-sig")

# 격자별
wide = ov.pivot_table(index="gid", columns="도로 종류", values="칸 안 길이_m", aggfunc="sum", fill_value=0).round(1)
wide.columns = [f"길이_{c}_m" for c in wide.columns]
main = ov.groupby(["gid", "도로 종류"])["칸 안 길이_m"].sum().reset_index().sort_values("칸 안 길이_m", ascending=False)
main_walk = ov[ov["보행 가능"] == "Y"].groupby(["gid", "도로 종류"])["칸 안 길이_m"].sum().reset_index().sort_values("칸 안 길이_m", ascending=False)
names = (ov[ov["ROAD_NAME"].astype(str).str.strip().isin(["", "-", "nan", "None"]) == False]
         .groupby(["gid", "ROAD_NAME"])["칸 안 길이_m"].sum().reset_index().sort_values("칸 안 길이_m", ascending=False)
         .groupby("gid")["ROAD_NAME"].apply(lambda s: ";".join(s.head(3))))
G = cells[["gid"]].copy()
G["주 도로 종류"] = G["gid"].map(main.drop_duplicates("gid").set_index("gid")["도로 종류"])
G["주 도로 종류(보행 가능 도로만)"] = G["gid"].map(main_walk.drop_duplicates("gid").set_index("gid")["도로 종류"])
G["도로 종류 수"] = G["gid"].map(ov.groupby("gid")["도로 종류"].nunique()).fillna(0).astype(int)
G["최대 차로 수"] = G["gid"].map(ov.groupby("gid")["LANES"].max())
G["주요 도로 이름"] = G["gid"].map(names)
G["지나는 관할표 이름"] = G["gid"].map(ov.groupby("gid")["관할표 이름"].apply(lambda s: ";".join(sorted(set(s)))))
G["지나는 노선"] = G["gid"].map(ov.dropna(subset=["노선"]).groupby("gid")["노선"].apply(lambda s: ";".join(sorted(set(s)))))
G = G.merge(wide, left_on="gid", right_index=True, how="left")
G.to_csv(C.OUT_DIR / "f02_grid_road_type.csv", index=False, encoding="utf-8-sig")

print(f"링크 {len(L):,}개 → out/f02_link_road_type.csv")
print(L["도로 종류"].value_counts().to_string())
print(f"\n격자 {len(G):,}칸 → out/f02_grid_road_type.csv (도로가 지나는 칸 {G['주 도로 종류'].notna().sum():,}칸)")
print(G["주 도로 종류"].value_counts(dropna=False).to_string())
