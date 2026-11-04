"""AI-03 배치: 좌표가 빈 행의 위치 글자로 좌표·격자를 찾는다 (A-07·C-06, 세은).

대상 표 (v2 칸 이름)
  parking    45 src_parking_enforce_place  enforce_place · gu          (DAT-05)  — --target 찾지못함|시도안함|전체
  signal     41 src_signal_controller      install_address → intersection_name · gu   (DAT-13)
  police     53 src_police_signal          intersection_name · police_station→구
  complaint  79 src_complaint              location_text · gu          (DAT-64)  — 결과는 out/ai03/에만 (저장소 X)
읽기: 공용 DB(.env RADAR_DB_*)에서 lat이 빈 행만. DB가 없으면 --csv <v2 CSV 폴더>
쓰기: DB는 건드리지 않는다. out/ai03/<표>_log.csv(행별 기록)·<표>_update.csv(반영할 것, v2 칸 이름)
      DB 반영은 확인(dry-run) 뒤 따로 한다. 실행 기록은 85 job_run에 남는다 (W05 공통 구조 11장).

사용법 (저장소 루트)
  uv sync --extra ai03
  uv run python -m scripts.ai03_locate parking --target 시도안함 --no-ai --start 0 --limit 7000
  uv run python -m scripts.ai03_locate signal
  uv run python -m scripts.ai03_locate police --csv C:\\...\\v2.1_통합테이블_CSV
옵션: --no-ai (LLM 끄기) · --offline (브이월드 끄기, 규칙·내부 대조만) · --start N --limit M
"""
import argparse
import os
import sys
from pathlib import Path

import pandas as pd

TABLES = {
    "parking":   {"table": "src_parking_enforce_place", "key": "row_id", "text": "enforce_place", "kind": "place",
                  "context": "주정차 단속장소", "data_ids": ["DAT-05"], "extra": ["enforce_cnt", "coord_method"]},
    "signal":    {"table": "src_signal_controller", "key": "row_id", "text": "intersection_name", "kind": "cross",
                  "context": "교통신호기 교차로명", "data_ids": ["DAT-13"], "extra": ["install_address"]},
    "police":    {"table": "src_police_signal", "key": "src_id", "text": "intersection_name", "kind": "cross",
                  "context": "경찰서 보행신호 교차로명", "data_ids": [], "extra": ["police_station"]},
    "complaint": {"table": "src_complaint", "key": "complaint_id", "text": "location_text", "kind": "place",
                  "context": "보행안전 민원 신고 위치", "data_ids": ["DAT-64"], "extra": ["coord_method"]},
}
POLICE_GU = {"성남수정경찰서": "수정구", "성남중원경찰서": "중원구", "분당경찰서": "분당구"}


def load_source(name: str, csv_dir: str | None) -> pd.DataFrame:
    t = TABLES[name]
    cols = [t["key"], t["text"], "lat"] + (["gu"] if name != "police" else []) + t["extra"]
    if csv_dir:
        f = next(Path(csv_dir).glob(f"[0-9][0-9]_{t['table']}.csv"))
        d = pd.read_csv(f, usecols=cols, low_memory=False)
    else:
        from app.core import db
        if not db.is_configured():
            sys.exit("DB 접속 정보가 없습니다 (.env RADAR_DB_*). 또는 --csv <v2 CSV 폴더>를 주세요.")
        sql = f"SELECT {', '.join('`' + c + '`' for c in cols)} FROM `{t['table']}` WHERE lat IS NULL"
        d = pd.DataFrame(db.read_only(sql))
    d = d[d["lat"].isna()].copy()
    if name == "police":
        d["gu"] = d["police_station"].map(POLICE_GU)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("table", choices=TABLES)
    ap.add_argument("--target", default="전체", help="parking: 찾지못함 | 시도안함 | 전체")
    ap.add_argument("--csv"); ap.add_argument("--start", type=int, default=0); ap.add_argument("--limit", type=int)
    ap.add_argument("--no-ai", action="store_true"); ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    if a.no_ai:
        os.environ["AI03_LLM"] = "off"
    from app.core.job_run import track
    from app.services.ai03 import config as C, llm, pipeline, validate
    t = TABLES[a.table]
    llm.check_policy(t["context"], t["data_ids"])
    if a.offline:
        pipeline.USE_VWORLD = False

    src = load_source(a.table, a.csv)
    if a.table == "parking" and a.target != "전체":
        src = src[src["coord_method"].astype(str).str.startswith("시도" if a.target == "시도안함" else "찾지")]
    if a.table == "complaint":                       # 위치 칸 변환이 실패한 민원만 (본문 위치는 별도 배치)
        src = src[src["coord_method"].astype(str).str.contains("못 찾음|도로 이름만")]
    by = ["gu", t["text"]]
    uniq = src.groupby(by, dropna=False).size().rename("n").reset_index()
    if "enforce_cnt" in src:
        uniq = uniq.merge(src.groupby(by, dropna=False)["enforce_cnt"].sum().reset_index(), on=by)
        uniq = uniq.sort_values("enforce_cnt", ascending=False)
    uniq = uniq.iloc[a.start:a.start + a.limit] if a.limit else uniq.iloc[a.start:]
    addr = src.drop_duplicates(by).set_index(by)["install_address"] if "install_address" in src else None
    tag = f"{a.table}" + (f"_{a.target}" if a.target != "전체" else "") + (f"_{a.start}" if a.start or a.limit else "") \
        + ("_noai" if a.no_ai else "")
    print(f"대상 {len(src):,}행 → 위치 글자 {len(uniq):,}개 (순서 {a.start}~)")

    logs = []
    with track("좌표", f"AI-03 {t['table']} {tag}", module="AI-03") as job:
        job.log(f"위치 글자 {len(uniq)}개를 처리합니다")
        for i, r in enumerate(uniq.itertuples(index=False), 1):
            gu = r.gu if isinstance(r.gu, str) else None
            text = getattr(r, t["text"])
            try:
                res = None
                if addr is not None:
                    a_ = addr.get((r.gu, text))
                    if isinstance(a_, str) and a_.strip():
                        res = pipeline.by_address(a_, gu)
                if res is None:
                    res = (pipeline.process(text, gu, t["context"], profile="교차로") if t["kind"] == "cross"
                           else pipeline.process_place(text, gu, t["context"]))
            except Exception as e:
                from app.services.ai03 import vworld
                if isinstance(e, vworld.VWorldError):
                    job.warn(f"브이월드 오류로 {i - 1}개에서 멈춤 — 다음에 --start {a.start + i - 1}부터")
                    break
                res = {"상태": "에러", "단계": "에러"}
            logs.append({"gu": r.gu, "text": text, "rows": r.n, **res})
            if i % 100 == 0:
                print(f"  {i}/{len(uniq)}"); llm.save_cache()
                if pipeline.USE_VWORLD:
                    from app.services.ai03 import vworld; vworld.save_cache()
        llm.save_cache()
        if pipeline.USE_VWORLD:
            from app.services.ai03 import vworld; vworld.save_cache()
        log = pd.DataFrame(logs)
        ok = log[(log.get("상태") == "성공") & ~((log.get("단서일치") == False) | (log.get("신뢰도") == "낮음"))].copy()
        job.rows(len(ok))
        job.log(f"성공 {len(ok)}개 (반영 보류 {int(((log.get('상태') == '성공')).sum()) - len(ok)}개)")

    log.to_csv(C.OUT / f"{tag}_log.csv", index=False, encoding="utf-8-sig")
    grid = pd.read_csv(C.DATA / "grid_cell.csv").set_index("gid")
    m = src.merge(ok.rename(columns={"gu": "gu", "text": t["text"]}), on=by)
    api = m.get("사용_API", pd.Series("", index=m.index)).astype(str)
    acc = ["보통 (AI-03 주소 검색)" if (s == "규칙+주소검색" or ("주소" in a_ and "장소" not in a_)) else
           "낮음 (AI-03 장소 이름 검색·내부 대조 — 근처 건물 좌표)" for s, a_ in zip(m["단계"].astype(str), api)]
    up = pd.DataFrame({t["key"]: m[t["key"]], "lat": m["위도"], "lon": m["경도"], "gid": m["gid"],
                       "grid_no": m["gid"].map(grid["g_no"]), "gu_by_coord": m["gid"].map(grid["gu_center"]),
                       "admin_dong_by_coord": m["gid"].map(grid["admin_dong_center"]),
                       "coord_method": "AI-03 " + m["단계"].astype(str) + " — " + api + " — 검색어 '" +
                                       m["검색어"].astype(str) + "' → " + m["결과_이름"].astype(str),
                       "coord_accuracy": acc})
    if a.table == "police":
        up = up.drop(columns=["grid_no", "gu_by_coord", "admin_dong_by_coord", "coord_accuracy"]).rename(
            columns={"coord_method": "location_method"})
    up.to_csv(C.OUT / f"{tag}_update.csv", index=False, encoding="utf-8-sig")
    print(log["상태"].value_counts().to_string())
    print(f"\n반영할 행 {len(up):,} → out/ai03/{tag}_update.csv (DB는 아직 안 바뀜)")


if __name__ == "__main__":
    main()
