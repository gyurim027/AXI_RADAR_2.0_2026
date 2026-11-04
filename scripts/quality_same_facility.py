"""A-08 같은 시설 묶기 — 고치지 않고 묶음 번호만 붙여 운영자가 확인 (A-06과 같은 원칙).

좌표가 있는 원천 표마다, 같은 시설로 보이는 행을 묶는다.
  ① 내용이 같은 행     키·연번·기준일만 다르고 나머지 칸이 모두 같음  (41·42의 dup_suspect와 같은 규칙)
  ② 같은 이름·같은 자리  이름이 같고(공백·괄호 무시) 서로 30m 안
  ③ 같은 자리·다른 이름  좌표가 5m 안인데 이름이 다름 → 같은 시설인지 확인 필요
                         ('확인 필요'로만 표시). 정확도 '낮음' 좌표(AI-03이 장소 이름 검색으로 찾은 근처 건물 좌표)는
                         역·건물 하나에 여러 이름이 한 점으로 모이므로 ③ 판단에서 뺀다 (②·① 은 그대로).
②·③은 '한 곳 = 한 줄'인 시설 표에만 적용한다. 버스정류장(양방향), 경찰 신호(횡단보도별),
과속방지턱·보안등·신호등·CCTV처럼 한 자리에 여러 개가 정상인 표는 ①만 본다.
묶음마다 대표 행(키가 가장 작은 행)을 정하고, 나머지는 '대표와 같음'으로 표시한다.

사용법 (저장소 루트에서)
  uv run python -m scripts.quality_same_facility [--csv <v2 CSV 폴더>]
결과 (out/grid/)
  a08_groups.csv    표·행 키·묶음 ID·유형·대표 행 키·거리(m)·이름 (+ 확인·처리 칸)
  a08_summary.csv   표 × 유형 묶음 수·행 수
"""
import re
import numpy as np
import sys
import pandas as pd
from app.services.grid import config as C, source as S
if "--csv" in sys.argv:                          # DB 대신 v2 CSV 폴더 읽기
    S.use_csv(sys.argv[sys.argv.index("--csv") + 1])
from app.services.quality.issue_format import to_issue

NAME_COLS = ["intersection_name", "install_place", "enforce_place", "facility_name", "name", "place_name", "stop_name",
             "location_text", "spot_name", "install_location", "road_or_location", "address", "install_address"]
SKIP_LOW = {}          # 표 이름 → 정확도 '낮음' 좌표라 ③에서 뺀 쌍 수 (끝에 출력)
SKIP = {"src_complaint", "src_lux_point", "src_road_hazard"}     # 민원(79 dup_flag)·이동 측정·탐지 기록은 '시설'이 아님
# 한 곳 = 한 줄이어야 하는 시설 표 → ①②③ 모두
FACILITY = {"src_child_facility", "src_elder_facility", "src_senior_center", "src_disabled_facility", "src_hump_crosswalk",
            "src_signal_controller", "src_parking_enforce_place", "src_yellow_carpet_history", "src_ped_hotspot_5y",
            "src_crosswalk", "src_floor_signal"}
# 그 밖(버스정류장 양방향, 경찰 신호 횡단보도별, 과속방지턱·보안등·신호등·CCTV 등 여러 개가 정상인 장치, 연도별로 반복되는 다발지)
#   → ① 내용이 같은 행만
IGNORE = re.compile(r"^(row_id|src_id|seq_no|.*_no|data_ref_date|upload_id|db_.*|dup_suspect)$")


def norm_name(s: pd.Series) -> pd.Series:
    return s.astype(str).str.replace(r"\(.*?\)|\s|[·.,\-]", "", regex=True).str.lower().where(s.notna())


def xy(lat, lon):
    la = np.radians(lat.mean())
    return np.c_[lon.to_numpy() * 111320 * np.cos(la), lat.to_numpy() * 110540]


def groups_in(name: str, d: pd.DataFrame, key: str):
    out = []                                                          # (행 키, 유형, 대표 키, 거리, 이름)
    d = d.assign(lat=pd.to_numeric(d["lat"], errors="coerce"), lon=pd.to_numeric(d["lon"], errors="coerce"))
    has = d["lat"].between(37.2, 37.6) & d["lon"].between(126.9, 127.3)     # 범위 밖 좌표는 A-06이 따로 표시
    d = d[has].copy()
    if len(d) < 2:
        return out
    nc = next((c for c in NAME_COLS if c in d.columns), None)
    d["_nm"] = norm_name(d[nc]) if nc else None
    P = xy(d["lat"], d["lon"])
    # 정확도 '낮음'(장소 이름 검색·근처 건물 좌표)인 행 — ③ 같은 자리·다른 이름 판단에서만 뺀다
    low = (d["coord_accuracy"].astype(str).str.startswith("낮음").to_numpy()
           if "coord_accuracy" in d.columns else np.zeros(len(d), dtype=bool))
    skipped_low = 0
    # ① 내용이 같은 행
    cols = [c for c in d.columns if not IGNORE.match(c) and not c.startswith("_")]
    sig = pd.util.hash_pandas_object(d[cols].astype(str), index=False)
    for _, g in d.groupby(sig):
        if len(g) > 1:
            rep = g[key].min()
            out += [(k, "① 내용이 같은 행", rep, 0.0, g[nc].iloc[0] if nc else "") for k in g[key] if k != rep]
    done = {r[0] for r in out}
    if name not in FACILITY:
        return out
    # ②·③ 거리 기준 (같은 gid와 이웃 칸만 비교해 빠르게)
    keys, names = d[key].to_numpy(), d["_nm"].to_numpy() if nc else np.array([None] * len(d))
    order = np.lexsort((keys.astype(str), P[:, 1], P[:, 0]))      # x → y → 키 순으로 항상 같은 순서 (컴퓨터마다 결과가 같게)
    for a_i in range(len(order)):
        i = order[a_i]
        for b_i in range(a_i + 1, len(order)):
            j = order[b_i]
            if P[j, 0] - P[i, 0] > 30:
                break
            dist = float(np.hypot(*(P[i] - P[j])))
            if dist > 30:
                continue
            ki, kj = keys[i], keys[j]
            if kj in done or ki == kj:
                continue
            rep, oth = (ki, kj) if ki < kj else (kj, ki)
            same_nm = names[i] is not None and names[i] == names[j]
            if same_nm:
                out.append((oth, "② 같은 이름·같은 자리", rep, round(dist, 1), d[nc].iloc[i]))
                done.add(oth)
            elif dist <= 5:
                if low[i] or low[j]:
                    skipped_low += 1                      # 낮음 좌표는 한 점에 모이기 쉬워 ③에서 제외
                    continue
                out.append((oth, "③ 같은 자리·다른 이름 (확인 필요)", rep, round(dist, 1),
                            f"{d[nc].iloc[i]} / {d[nc].iloc[j]}" if nc else ""))
    if skipped_low:
        SKIP_LOW[name] = skipped_low
    return out


if __name__ == "__main__":
    rows = []
    for name in S.tables():
        if not name.startswith("src_") or name in SKIP:
            continue
        head = S.columns(name)
        if "lat" not in head:
            continue
        d = S.read(name)
        key = head[0]
        for k, t, rep, dist, nm in groups_in(name, d, key):
            rows.append((name, k, t, rep, dist, nm))
    G = pd.DataFrame(rows, columns=["표", "행 키", "유형", "대표 행 키", "거리(m)", "이름"])
    G.insert(1, "묶음 ID", G["표"] + ":" + G["대표 행 키"].astype(str))
    PK = {t: S.columns(t)[0] for t in set(G["표"])}
    I = to_issue(G.rename(columns={"유형": "검사"}).assign(
        값=G["이름"].astype(str), 비고="대표 행 " + G["대표 행 키"].astype(str) + "와 같음 (" + G["거리(m)"].astype(str) + "m)"), "A-08", PK)
    I.to_csv(C.OUT_DIR / "a08_groups.csv", index=False, encoding="utf-8-sig")
    S = G.groupby(["표", "유형"]).agg(묶음수=("묶음 ID", "nunique"), 행수=("행 키", "size")).reset_index()
    S.to_csv(C.OUT_DIR / "a08_summary.csv", index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 200)
    print(S.to_string(index=False))
    if SKIP_LOW:
        print("\n정확도 '낮음' 좌표라 ③에서 뺀 쌍: " + ", ".join(f"{t} {n:,}쌍" for t, n in SKIP_LOW.items()))
    print(f"\n저장: {C.OUT_DIR / 'a08_groups.csv'} ({len(G):,}행, 묶음 {G['묶음 ID'].nunique():,}개), {C.OUT_DIR / 'a08_summary.csv'}")
