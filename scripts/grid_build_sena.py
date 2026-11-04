"""B-01~B-06 실행: build_grid_table.py(세은 v1.1.1)를 원본 폴더 기준으로 돌리고, v2 칸 이름으로 바꿔 저장한다.

사용법 (저장소 루트에서, uv run python -m scripts.<이 파일 이름>)
  uv run python -m scripts.grid_build_sena            # 계산 + v2 이름으로 저장
  uv run python -m scripts.grid_build_sena --compare  # 위 + v2의 05 grid_feature와 칸별 비교

결과
  out/grid_feature_sena.csv        v2 칸 이름(gid 기준) — 세은 담당 83열
  out/grid_feature_sena_비교.csv    --compare일 때 칸별 일치율
"""
import sys
import pandas as pd
from app.services.grid import config as C, source as S
if "--csv" in sys.argv:                          # DB 대신 v2 CSV 폴더 읽기
    S.use_csv(sys.argv[sys.argv.index("--csv") + 1])
from app.services.grid import build_grid_table as B

# build_grid_table.py는 자기 위치를 기준으로 원본을 찾으므로, 원본 폴더로 바꿔 준다
B.BASE = C.RAW_DIR
B.OUT = C.OUT_DIR / "build_grid_raw"
B.OUT.mkdir(exist_ok=True)

if not C.RAW_DIR.exists():
    sys.exit(f"원본 폴더가 없습니다: {C.RAW_DIR}\n→ .env의 RADAR_GRID_RAW_DIR에 '최종사용할 데이터' 폴더 경로를 넣어 주세요.")

T = B.main()                                   # 한글 칸 이름(ID_구, CTX_링크수 …)

# 한글 칸 → v2 영어 칸
mp = pd.read_csv(C.DATA_DIR / "grid_column_map.csv")
rename = dict(zip(mp["build_grid_table_칸"], mp["v2_05_칸"]))
out = T.rename(columns=rename)

# v1.7부터 어린이집·유치원은 공식 목록(v2 26_src_child_facility)으로 센다 — 원본 코드의 통합 CSV 대신
cf = S.read("src_child_facility")
cf = cf[cf["gid"].notna()]
for col, t in (("vul_daycare_cnt", "어린이집"), ("vul_kindergarten_cnt", "유치원")):
    cnt = cf[cf["type"] == t].groupby("gid").size()
    out[col] = out["ID_gid"].map(cnt).fillna(0)
print("어린이집·유치원: v2 26_src_child_facility(공식 목록)로 다시 셈")
out.to_csv(C.OUT_DIR / "grid_feature_sena.csv", index=False, encoding="utf-8-sig")
print(f"\n저장: out/grid_feature_sena.csv ({len(out):,}칸 × {len(out.columns)}열, v2 칸 이름)")

if "--compare" in sys.argv:
    v2 = S.read("grid_feature")
    m = out.merge(v2, on="ID_gid", suffixes=("", "__v2"))
    rows = []
    for c in out.columns:
        if c == "ID_gid" or c + "__v2" not in m.columns:
            continue
        a, b = m[c], m[c + "__v2"]
        an, bn = pd.to_numeric(a, errors="coerce"), pd.to_numeric(b, errors="coerce")
        if an.notna().any():
            same = ((an - bn).abs() < 1e-6) | (an.isna() & bn.isna())
        else:
            same = (a.fillna("").astype(str) == b.fillna("").astype(str))
        rows.append({"칸": c, "일치율": round(same.mean(), 4), "다른 칸 수": int((~same).sum())})
    r = pd.DataFrame(rows).sort_values("일치율")
    # 예전 결과(83열)에 있었는데 이번에 안 만들어진 칸 = 원본 파일을 못 찾아 건너뛴 칸
    missing = [v for k, v in rename.items() if v not in out.columns]
    if missing:
        print(f"\n⚠️ 이번에 안 만들어진 칸 {len(missing)}개 (원본 파일을 못 찾았을 가능성): {missing}")
    r.to_csv(C.OUT_DIR / "grid_feature_sena_비교.csv", index=False, encoding="utf-8-sig")
    print(f"v2와 100% 같은 칸: {(r['일치율'] == 1).sum()} / {len(r)}")
    print(r[r["일치율"] < 1].to_string(index=False))
