"""A-06 이상한 값 찾기 — 고치지 않고 표시만, 운영자가 확인 (A-06 예외).

검사 (좌표가 있는 모든 원천·판정 표)
  성남 격자 밖     좌표가 공식 250m 격자(01 grid_cell) 2,406칸 어디에도 들지 않음
  좌표 범위 이상   위도 37.2~37.6 / 경도 126.9~127.3 밖 (위경도 뒤바뀜 의심 포함)
  gid 불일치      적힌 gid와 좌표로 계산한 gid가 다름 (명세서 7장: EPSG:5179 → 250m)
  gid·좌표 짝 없음 좌표는 있는데 gid가 비었거나, gid는 있는데 좌표가 빔
  구 불일치       표에 적힌 구(신고·원천 주소)와 좌표가 있는 칸의 구가 다름
민원 전용
  구 불일치 → coord_accuracy를 '낮음'으로 표시할 목록 (C-07이 '낮음 제외' 값을 셀 때 씀)
  처리일 < 접수일, 접수일이 자료 기간 밖

사용법 (저장소 루트에서, uv run python -m scripts.<이 파일 이름>)
  python a06_anomaly.py [--ai03 ai03_updates]
결과
  out/a06_flags.csv                      표·행·검사·값 (운영자 확인 목록)
  out/a06_complaint_accuracy_low.csv     민원 coord_accuracy → '낮음' 표시 목록
  out/a06_summary.csv                    표 × 검사 건수
"""
import re
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from pyproj import Transformer
from app.services.grid import config as C, source as S
if "--csv" in sys.argv:                          # DB 대신 v2 CSV 폴더 읽기
    S.use_csv(sys.argv[sys.argv.index("--csv") + 1])
from app.services.quality.issue_format import to_issue

T = Transformer.from_crs(4326, 5179, always_xy=True)
CELL = 250


NB = {}          # gid → 자기 칸과 이웃 8칸의 구


def grid_index():
    g = S.read("grid_cell")
    x, y = T.transform(g["center_lon"].to_numpy(), g["center_lat"].to_numpy())
    i, j = np.floor(x / CELL).astype(int), np.floor(y / CELL).astype(int)
    key = i * 100000 + j
    pos = dict(zip(zip(i, j), g["gu_center"]))
    for gid, a, b in zip(g["gid"], i, j):
        NB[gid] = {pos.get((a + da, b + db)) for da in (-1, 0, 1) for db in (-1, 0, 1)} - {None}
    return dict(zip(key, g["gid"])), g.set_index("gid")["gu_center"]


def gid_of(lat, lon, idx):
    x, y = T.transform(lon.to_numpy(), lat.to_numpy())
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = np.where(ok, x, 0.0), np.where(ok, y, 0.0)
    key = np.where(ok, np.floor(x / CELL).astype(np.int64) * 100000 + np.floor(y / CELL).astype(np.int64), -1)
    return pd.Series([idx.get(k) if o else None for k, o in zip(key, ok)], index=lat.index)


_DONG = None


def dong_boundary():
    """원본 폴더의 SGIS 행정동 경계(B-06과 같은 파일)를 읽어 구 경계로 쓴다. 없으면 None."""
    global _DONG
    if _DONG is not None:
        return _DONG if len(_DONG) else None
    try:
        import geopandas as gpd
        from app.services.grid import build_grid_table as B
        B.BASE = C.RAW_DIR
        p = B.first(["dong"], (".shp",), exclude=("성남",)) or B.first(["행정동"], (".shp",))
        d = B.read_shp_auto(p).to_crs(4326)
        cc = next(c for c in d.columns if c.upper() in ("ADM_CD", "ADM_DR_CD"))
        d = d[d[cc].astype(str).str.startswith(("31021", "31022", "31023"))]
        d["구_경계"] = d[cc].astype(str).str[:5].map({"31021": "수정구", "31022": "중원구", "31023": "분당구"})
        _DONG = d[["구_경계", "geometry"]]
        print(f"[구 경계] {p.name} — 좌표가 들어 있는 행정동 경계로 구를 정함")
    except Exception as e:
        print(f"[구 경계] 행정동 경계를 못 읽어 칸 중심 구로 비교 (경계 근처는 따로 표시): {str(e)[:80]}")
        _DONG = pd.DataFrame()
        return None
    return _DONG


def gu_by_point(lat, lon):
    d = dong_boundary()
    if d is None:
        return None
    import geopandas as gpd
    pts = gpd.GeoDataFrame(index=lat.index, geometry=gpd.points_from_xy(lon, lat), crs=4326)
    j = gpd.sjoin(pts[lat.notna()], d, how="left", predicate="within")
    return j[~j.index.duplicated()]["구_경계"].reindex(lat.index)


def gu_norm(s):
    return s.astype(str).str.extract(r"(수정구|중원구|분당구)")[0]


def check_table(name: str, idx, gu_of_gid, flags: list):
    head = S.columns(name)
    key = head[0]
    use = [c for c in [key, "lat", "lon", "gid", "gu", "coord_accuracy"] if c in head]
    d = S.read(name, usecols=use)
    if d.empty:
        return
    lat, lon = pd.to_numeric(d["lat"], errors="coerce"), pd.to_numeric(d["lon"], errors="coerce")
    has = lat.notna() & lon.notna()

    def add(mask, check, val, detail=""):
        for k, v in zip(d.loc[mask, key], val[mask] if isinstance(val, pd.Series) else [val] * int(mask.sum())):
            flags.append((name, k, check, v, detail))

    bad = has & ~(lat.between(37.2, 37.6) & lon.between(126.9, 127.3))
    swap = bad & lat.between(126.9, 127.3) & lon.between(37.2, 37.6)
    add(bad, "좌표 범위 이상", lat.round(6).astype(str) + "," + lon.round(6).astype(str))
    add(swap, "위경도 뒤바뀜 의심", lat.round(6).astype(str) + "," + lon.round(6).astype(str))
    calc = gid_of(lat.where(has), lon.where(has), idx)
    add(has & ~bad & calc.isna(), "성남 격자 밖", lat.round(6).astype(str) + "," + lon.round(6).astype(str))
    if "gid" in d:
        add(has & d["gid"].notna() & calc.notna() & (calc != d["gid"]), "gid 불일치", d["gid"].astype(str) + " → 좌표상 " + calc.astype(str))
        add(has & d["gid"].isna() & calc.notna(), "gid 빔 (좌표 있음)", calc.astype(str))
        add(~has & d["gid"].notna(), "좌표 빔 (gid 있음)", d["gid"].astype(str))
    gu_mis = pd.Series(False, index=d.index)
    if "gu" in d:
        g_src = gu_norm(d["gu"])
        g_pt = gu_by_point(lat.where(has), lon.where(has))
        if g_pt is not None:                                   # 좌표가 들어 있는 행정동 경계의 구
            gu_mis = has & g_src.notna() & g_pt.notna() & (g_src != g_pt)
            add(gu_mis, "구 불일치", "적힌 구 " + g_src.astype(str) + " / 좌표 구 " + g_pt.astype(str))
        else:                                                  # 경계 파일이 없으면 칸 중심 구 + 이웃 칸 확인
            g_cell = calc.map(gu_of_gid)
            mis = has & g_src.notna() & g_cell.notna() & (g_src != g_cell)
            near = mis & pd.Series([any(NB.get(c, set()) & {s}) if isinstance(c, str) else False
                                    for c, s in zip(calc, g_src)], index=d.index)
            gu_mis = mis & ~near
            add(gu_mis, "구 불일치", "적힌 구 " + g_src.astype(str) + " / 칸 구 " + g_cell.astype(str))
            add(near, "구 불일치(경계 근처·확인 필요)", "적힌 구 " + g_src.astype(str) + " / 칸 구 " + g_cell.astype(str),
                "칸 중심 기준이라 경계 근처는 실제로 같은 구일 수 있음 — '낮음' 표시 안 함")
    return name, d, gu_mis


if __name__ == "__main__":
    idx, gu_of_gid = grid_index()
    flags = []
    low = None
    for name in S.tables():
        if "lat" not in S.columns(name):
            continue
        r = check_table(name, idx, gu_of_gid, flags)
        if r and r[0] == "src_complaint":
            _, d, gu_mis = r
            low = d.loc[gu_mis & (d["coord_accuracy"] != "낮음"), ["complaint_id", "coord_accuracy"]].rename(
                columns={"coord_accuracy": "coord_accuracy_지금"}).assign(coord_accuracy_표시="낮음", 이유="신고 주소 구 ≠ 좌표 구")
    # 민원 날짜
    c = S.read("src_complaint", usecols=["complaint_id", "received_date", "processed_date", "data_period"])
    rd, pd_ = pd.to_datetime(c["received_date"], errors="coerce"), pd.to_datetime(c["processed_date"], errors="coerce")
    per = c["data_period"].astype(str).str.extract(r"(\d{4}-\d\d-\d\d)~(\d{4}-\d\d-\d\d)")
    m1 = rd.notna() & pd_.notna() & (pd_ < rd)
    m2 = rd.notna() & ((rd < pd.to_datetime(per[0])) | (rd > pd.to_datetime(per[1])))
    flags += [("src_complaint", k, "처리일 < 접수일", f"{a} / {b}", "") for k, a, b in zip(c.loc[m1, "complaint_id"], c.loc[m1, "received_date"], c.loc[m1, "processed_date"])]
    flags += [("src_complaint", k, "접수일이 자료 기간 밖", str(a), "") for k, a in zip(c.loc[m2, "complaint_id"], c.loc[m2, "received_date"])]

    F = pd.DataFrame(flags, columns=["표", "행 키", "검사", "값", "비고"])
    # 민원은 원본 위치(raw_position)와 upload_id가 있어 같이 적는다
    cx = S.read("src_complaint", usecols=["complaint_id", "raw_position", "upload_id"]).set_index("complaint_id")
    isc = F["표"] == "src_complaint"
    raw = F["행 키"].where(isc).map(cx["raw_position"]).fillna("").astype(str)      # '2026년 파일 · 03월 시트 · 번호 10102'
    F["원본 파일"] = raw.str.replace(r"\s*·\s*번호\s*\d+$", "", regex=True)
    F["원본 행 번호"] = raw.str.extract(r"번호\s*(\d+)$")[0].fillna("")
    F["upload_id"] = F["행 키"].where(isc).map(cx["upload_id"]).astype("Int64").astype(str).replace("<NA>", "")
    PK = {t: S.columns(t)[0] for t in set(F["표"])}
    to_issue(F, "A-06", PK).to_csv(C.OUT_DIR / "a06_flags.csv", index=False, encoding="utf-8-sig")
    S = F.groupby(["표", "검사"]).size().rename("건수").reset_index()
    S.to_csv(C.OUT_DIR / "a06_summary.csv", index=False, encoding="utf-8-sig")
    if low is not None:
        low.to_csv(C.OUT_DIR / "a06_complaint_accuracy_low.csv", index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 200)
    print(S.pivot_table(index="표", columns="검사", values="건수", fill_value=0).to_string())
    print(f"\n저장: out/a06_flags.csv ({len(F):,}건), out/a06_summary.csv"
          + (f", out/a06_complaint_accuracy_low.csv (민원 {len(low):,}건 '낮음' 표시)" if low is not None else ""))
