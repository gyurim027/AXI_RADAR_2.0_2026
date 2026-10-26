"""05 grid_feature(108열) · 06 grid_feature_ng(11열) 전체 다시 만들기 — B-02·B-03·B-07 (세은).

순서 (은경 docs/grid/ext_columns.md와 같음)
  ① 세은 83열: scripts/grid_build_sena.py 결과(out/grid/grid_feature_sena.csv, 어린이집·유치원은 26 공식 목록)
  ② EXT_ 21열 + 06 센 값 6열: 은경 app/services/grid/ext_columns.py (v2 CSV를 DB처럼 읽음)
  ③ 포트홀·시선유도봉 4열: 83 src_road_hazard를 gid별로 셈 (탐지 행 수, 탐지 날짜 수)
  ④ 06 보도 면적·폭 5칸: 은경님이 수치지형도로 만든 값을 그대로 이어 씀

사용법 (저장소 루트에서, uv run python -m scripts.<이 파일 이름>)
  python build_grid_feature.py --compare            # 지금 v2와 칸별 비교
  python build_grid_feature.py --ai03 <폴더>         # AI-03 update 파일을 원천 표에 넣고 다시 셈 → 전후 비교

결과: out/05_grid_feature_new.csv, out/06_grid_feature_ng_new.csv (+ --ai03이면 out/ai03_전후비교.csv)
"""
import sys
from pathlib import Path
import pandas as pd
from app.services.grid import config as C, source as S
if "--csv" in sys.argv:                          # DB 대신 v2 CSV 폴더 읽기
    S.use_csv(sys.argv[sys.argv.index("--csv") + 1])



def apply_ai03(upd_dir: Path) -> dict:
    """ai03_v2_update_*.csv를 원천 표에 덮어쓴다. 좌표가 빈 행만 (기존 좌표는 그대로)."""
    out = {}
    for table, f, key in (("src_parking_enforce_place", "ai03_v2_update_45_parking.csv", "row_id"),
                          ("src_signal_controller", "ai03_v2_update_41_signal_controller.csv", "row_id")):
        p = upd_dir / f
        if not p.exists():
            continue
        src = S.read(table, dtype=str, keep_default_na=False, na_values=[""])
        u = pd.read_csv(p, dtype=str)
        u = u[u[key].isin(src.loc[src["lat"].isna(), key])]                  # 빈칸 행만
        src = src.set_index(key)
        for c in ("lat", "lon", "gid", "coord_method", "coord_accuracy"):
            if c in u.columns and c in src.columns:
                src.loc[u[key], c] = u.set_index(key)[c]
        out[table] = src.reset_index()
        print(f"[AI-03] {table}: {len(u)}행 좌표 채움")
    return out


def build(overrides=None):
    sena = pd.read_csv(C.OUT_DIR / "grid_feature_sena.csv")
    if overrides and not S.using_csv():
        sys.exit("--ai03 미리 보기는 --csv <v2 CSV 폴더>와 함께 써 주세요 (DB는 바꾸지 않고 CSV로 셈)")
    S.install_db_shim(overrides)                     # CSV 모드면 ext_columns도 CSV로, DB 모드면 그대로 DB
    from app.services.grid.ext_columns import compute, compute_ng, COLUMNS, NG_COLUMNS
    ext = pd.DataFrame.from_dict(compute(), orient="index")[COLUMNS].rename_axis("ID_gid").reset_index()
    ng = pd.DataFrame.from_dict(compute_ng(), orient="index")[NG_COLUMNS].rename_axis("ID_gid").reset_index()
    rh = S.read("src_road_hazard")
    rh = rh[rh["gid"].notna()].assign(day=lambda d: d["detected_at"].astype(str).str[:10])
    hz = pd.DataFrame({"ID_gid": sena["ID_gid"]})
    for t, k in (("포트홀", "pothole"), ("시선유도봉", "delineator")):
        x = rh[rh["type"] == t]
        hz[f"cond_{k}_detect_cnt"] = hz["ID_gid"].map(x.groupby("gid").size()).fillna(0)
        hz[f"cond_{k}_detect_days"] = hz["ID_gid"].map(x.groupby("gid")["day"].nunique()).fillna(0)
    g05 = sena.merge(ext, on="ID_gid").merge(hz, on="ID_gid")
    order = S.columns("grid_feature")
    g05 = g05[[c for c in order if c in g05.columns]]
    ng_order = S.columns("grid_feature_ng")
    ng = ng[[c for c in ng_order if c in ng.columns]]
    return g05, ng


def compare(new: pd.DataFrame, old: pd.DataFrame) -> pd.DataFrame:
    m = new.merge(old, on="ID_gid", suffixes=("", "__old"))
    rows = []
    for c in new.columns:
        if c == "ID_gid" or c + "__old" not in m.columns:
            continue
        a, b = m[c], m[c + "__old"]
        an, bn = pd.to_numeric(a, errors="coerce"), pd.to_numeric(b, errors="coerce")
        same = (((an - bn).abs() < 1e-6) | (an.isna() & bn.isna())) if an.notna().any() else \
            (a.fillna("").astype(str) == b.fillna("").astype(str))
        rows.append({"칸": c, "일치율": round(same.mean(), 4), "바뀐 칸 수": int((~same).sum()),
                     "전 합계": round(bn.sum(), 1) if an.notna().any() else None,
                     "후 합계": round(an.sum(), 1) if an.notna().any() else None})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    if not (C.OUT_DIR / "grid_feature_sena.csv").exists():
        sys.exit("먼저 uv run python -m scripts.grid_build_sena 를 실행해 out/grid/grid_feature_sena.csv를 만들어 주세요.")
    v2_05 = S.read("grid_feature")
    v2_06 = S.read("grid_feature_ng")
    g05, g06 = build()
    g05.to_csv(C.OUT_DIR / "05_grid_feature_new.csv", index=False, encoding="utf-8-sig")
    g06.to_csv(C.OUT_DIR / "06_grid_feature_ng_new.csv", index=False, encoding="utf-8-sig")
    print(f"저장: out/05_grid_feature_new.csv ({len(g05)}칸 × {len(g05.columns)}열), out/06_grid_feature_ng_new.csv ({len(g06.columns)}열)")
    if "--compare" in sys.argv:
        for name, new, old in (("05", g05, v2_05), ("06", g06, v2_06)):
            r = compare(new, old)
            print(f"[{name}] v2와 100% 같은 칸: {(r['일치율'] == 1).sum()} / {len(r)}")
            if (r["일치율"] < 1).any():
                print(r[r["일치율"] < 1].to_string(index=False))
    if "--ai03" in sys.argv:
        upd = Path(sys.argv[sys.argv.index("--ai03") + 1])
        a05, _ = build(apply_ai03(upd))
        r = compare(a05, g05)
        r = r[r["바뀐 칸 수"] > 0]
        r.to_csv(C.OUT_DIR / "ai03_전후비교.csv", index=False, encoding="utf-8-sig")
        a05.to_csv(C.OUT_DIR / "05_grid_feature_ai03.csv", index=False, encoding="utf-8-sig")
        print("\n[AI-03 반영 전후] 바뀐 격자 칸")
        print(r.to_string(index=False))
