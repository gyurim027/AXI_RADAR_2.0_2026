# -*- coding: utf-8 -*-
"""
RADAR 250m 격자 통합 테이블 만들기 (v1.1.1 — 행정동 경계 글자 인코딩 자동 판별)

목적: 최종 사용 데이터(01_공간기준 ~ 05_이용자_인구, 완화시설은 99_보조_검증자료)를
      공식 250m 격자 2,406칸 위에 '역할별 열'로 한 장의 표로 합칩니다.
원칙: 점수·가중치로 합산하지 않습니다. 열 이름의 앞부분이 역할입니다.
  ID_   식별·위치        CTX_  도로·지형 구조(맥락)   RES_  사고 결과
  COND_ 위험 조건        EXP_  노출                   VUL_  취약 이용자·영향 조정
  MIT_  완화·안전시설(위험요인이 아님)

사용법(이 파일을 '최종사용할 데이터' 폴더 맨 위에 두고):
    python build_grid_table.py
결과: output/RADAR_격자테이블_250m.csv, 컬럼설명.csv, 점검표.csv
필요 패키지: pandas, geopandas, shapely, rasterio, pyproj
다시 돌리는 경우: 보안등 파일을 03_보행환경시설에 넣거나, SGIS 행정동 경계가 01_공간기준에 있으면
                  해당 열(COND_보안등_*, ID_행정동코드, VUL_동_*)이 자동으로 채워집니다.
"""
import json, re, sys, warnings
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely import wkt
from shapely.geometry import Polygon, shape
warnings.filterwarnings("ignore")

# 저장소 안에서는 원본 폴더·결과 폴더를 설정에서 받는다 (scripts/grid_build_sena.py가 정함)
try:
    from app.services.grid import config as _C
    BASE, OUT = _C.RAW_DIR, _C.OUT_DIR / "build_grid_raw"
except Exception:                                   # 원래처럼 '최종사용할 데이터' 폴더에 두고 단독 실행할 때
    BASE = Path(__file__).resolve().parent
    OUT = BASE / "output"
CRS_M, CELL = 5179, 250
LAT_R, LON_R = (37.3, 37.55), (127.0, 127.25)
QA, DOC = [], []          # 점검표, 컬럼 설명


# ------------------------------------------------------------------ 파일 찾기
def norm(s):
    return re.sub(r"[\s_().\-·]", "", str(s)).lower()

SKIP_WORDS = ("백업", "삭제가능", "archive", "backup", "원본")
def skip_dir(name, aux):
    n = str(name).lower()
    if any(w in n for w in SKIP_WORDS):
        return True
    if aux:
        return False
    return n.startswith("99_") or "보조" in n or "검증" in n

def find_files(patterns, exts, exclude=(), aux=False):
    out = []
    for root, dirs, files in __import__("os").walk(BASE):
        dirs[:] = [d for d in dirs if d not in (".venv", "__pycache__", ".git", "output") and not skip_dir(d, aux)]
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() not in exts:
                continue
            n = norm(f)
            if all(norm(k) in n for k in patterns) and not any(norm(x) in n for x in exclude):
                out.append(p)
    return sorted(out)

def first(patterns, exts, exclude=(), aux=False):
    fs = find_files(patterns, exts, exclude, aux)
    return fs[-1] if fs else None

def read_any(p):
    p = Path(p)
    for enc in ("utf-8-sig", "cp949"):
        for sep in (",", "\t"):
            try:
                d = pd.read_csv(p, encoding=enc, sep=sep, dtype=str)
                if len(d.columns) > 1:
                    return d
            except Exception:
                pass
    raise ValueError(f"읽을 수 없음: {p.name}")

def split_json(raw):
    dec, out, t = json.JSONDecoder(), [], raw.lstrip("\ufeff")
    while t.strip():
        t = t.lstrip(); o, i = dec.raw_decode(t); out.append(o); t = t[i:]
    return out

def find_records(o):
    if isinstance(o, list) and o and all(isinstance(x, dict) for x in o):
        return o
    if isinstance(o, dict):
        for k in ("item", "data", "row", "items", "body", "response"):
            if k in o:
                r = find_records(o[k])
                if r:
                    return r
        for v in o.values():
            r = find_records(v)
            if r:
                return r
    return None

def read_json_records(p):
    rows = []
    for o in split_json(Path(p).read_text(encoding="utf-8-sig")):
        rows += find_records(o) or []
    return pd.DataFrame(rows)

def pick(cols, names):
    low = {str(c).lower(): c for c in cols}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    return None

def to_num(s):
    return pd.to_numeric(pd.Series(s).astype(str).str.replace(",", "").str.strip(), errors="coerce")

def points_df(df, lat=None, lon=None):
    lat = lat or pick(df.columns, ["위도", "latitude", "lat", "WGS84위도", "위도(LATITUDE)"])
    lon = lon or pick(df.columns, ["경도", "longitude", "lon", "lng", "WGS84경도", "경도(LONGITUDE)"])
    if lat is None or lon is None:
        return None
    la, lo = to_num(df[lat]), to_num(df[lon])
    ok = la.between(*LAT_R) & lo.between(*LON_R)
    g = gpd.GeoDataFrame(df[ok].copy(), geometry=gpd.points_from_xy(lo[ok], la[ok], crs=4326)).to_crs(CRS_M)
    return g

def cid_of(g):
    x, y = g.geometry.x.values, g.geometry.y.values
    return pd.Series([f"{int(a)}_{int(b)}" for a, b in zip(np.floor(x / CELL), np.floor(y / CELL))], index=g.index)



def read_shp_auto(path, name_cols=("ADM_NM", "ADM_DR_NM")):
    """shp 속성의 글자 인코딩을 자동으로 고른다(.cpg → utf-8 → cp949 순으로 시험).
    이름이 '동·읍·면·가·리·구·시·군'으로 끝나는 비율이 가장 높은 인코딩을 선택 — 인코딩이 틀리면 '신흥1동'이 '떊씎1룞'처럼 깨짐."""
    p = Path(path); encs = []
    cpg = p.with_suffix(".cpg")
    if cpg.exists():
        try: encs.append(cpg.read_text(errors="ignore").strip().lower().replace("utf8", "utf-8"))
        except Exception: pass
    encs += ["utf-8", "cp949"]
    best, best_score = None, -1.0
    for enc in dict.fromkeys(e for e in encs if e):
        try:
            g = gpd.read_file(p, encoding=enc)
        except Exception:
            continue
        nc = next((c for c in g.columns if c.upper() in name_cols), None)
        score = g[nc].astype(str).str.contains(r"(?:동|읍|면|가|리|구|시|군)$").mean() if nc else 0.0
        if score > best_score + 1e-9:
            best, best_score = g, score
        if score >= 0.95:
            break
    if best is None:
        best = gpd.read_file(p)
    return best

# ------------------------------------------------------------------ 격자
def load_grid():
    hits = [p for p in BASE.rglob("*") if p.suffix.lower() in (".zip", ".shp") and "output" not in p.parts
            and not any(skip_dir(x, False) for x in p.relative_to(BASE).parts[:-1])
            and ("b100" in p.name.lower() or p.name.lower() == "vl_blk.shp")]
    if not hits:
        sys.exit("공식 250m 격자(B100 zip)를 찾지 못했습니다. 01_공간기준에 두세요.")
    p = hits[0]
    g = gpd.read_file(f"zip://{p}", encoding="utf-8") if p.suffix.lower() == ".zip" else gpd.read_file(p, encoding="utf-8")
    g = g.to_crs(CRS_M) if g.crs else g.set_crs(CRS_M)
    b = g.geometry.bounds
    g["cid"] = [f"{int(np.floor((x + .5) / CELL))}_{int(np.floor((y + .5) / CELL))}" for x, y in zip(b.minx, b.miny)]
    g["pop"] = pd.to_numeric(g.get("val"), errors="coerce")
    print(f"[격자] {p.name}: {len(g):,}칸")
    return g[["cid", "gid", "pop", "geometry"]].reset_index(drop=True)


# ------------------------------------------------------------------ 기록 도우미
def add_col(S, name, role, series, meaning, source, how, period, caution):
    S[name] = series.reindex(S.index)
    DOC.append(dict(컬럼=name, 역할=role, 의미=meaning, 출처=source, 집계방법=how, 기준시점=period, 주의=caution))

def qa(name, n_in, n_use, n_in_grid, note=""):
    QA.append(dict(자료=name, 입력행=n_in, 사용행=n_use, 격자안=n_in_grid, 비고=note))

def count_points(S, g, name, role, meaning, source, period, caution, value=None, how="칸 안 점의 개수", fill0=True):
    if g is None or len(g) == 0:
        S[name] = np.nan
        DOC.append(dict(컬럼=name, 역할=role, 의미=meaning, 출처=source + " (파일 없음 — 비어 있음)", 집계방법=how, 기준시점=period, 주의=caution))
        return
    c = cid_of(g)
    s = (value.groupby(c).sum() if value is not None else c.value_counts())
    s = s[s.index.isin(S.index)]
    S[name] = s.reindex(S.index)
    if fill0:
        S[name] = S[name].fillna(0)
    DOC.append(dict(컬럼=name, 역할=role, 의미=meaning, 출처=source, 집계방법=how, 기준시점=period, 주의=caution))
    return int(c.isin(S.index).sum())


def main():
    cells = load_grid()
    S = pd.DataFrame(index=cells["cid"])
    S["ID_gid"] = cells.set_index("cid")["gid"]
    cen = cells.set_index("cid").geometry.centroid
    ll = gpd.GeoSeries(cen, crs=CRS_M).to_crs(4326)
    S["ID_중심위도"], S["ID_중심경도"] = ll.y.round(6), ll.x.round(6)
    S.insert(0, "ID_cid", S.index)
    for nm, mean in (("ID_cid", "칸 번호(좌표÷250). 우리가 만든 칸 번호"), ("ID_gid", "공식 칸 번호(국가지점번호형, 앞 2글자 '다사'=100km 격자)"), ("ID_중심위도", "칸 중심 위도(WGS84)"), ("ID_중심경도", "칸 중심 경도(WGS84)")):
        DOC.append(dict(컬럼=nm, 역할="식별", 의미=mean, 출처="국토통계 250m 격자(B100)", 집계방법="-", 기준시점="2025-10", 주의="cid와 gid는 경계가 같고 번호 규칙만 다름"))
    add_col(S, "EXP_칸총인구", "노출", cells.set_index("cid")["pop"], "칸 안 거주 총인구", "국토통계 250m 격자(B100)", "칸별 값", "2025-10", "'통계없음' 칸은 빈 값 — 0이 아님(1,300칸). 업무·상업지 낮 인구는 반영되지 않음")
    S["EXP_인구통계없음"] = S["EXP_칸총인구"].isna().astype(int)
    DOC.append(dict(컬럼="EXP_인구통계없음", 역할="노출", 의미="총인구 통계가 없는 칸이면 1", 출처="B100", 집계방법="총인구가 비었는지", 기준시점="2025-10", 주의="통계없음≠인구 0. 칸 자체는 지우지 않음"))

    # ---- 도로·교차로 구조 (링크·노드)
    lp, np_ = first(["성남", "링크"], (".shp",)), first(["성남", "노드"], (".shp",))
    links = None
    if lp is not None:
        links = gpd.read_file(lp, encoding="cp949").to_crs(CRS_M)
        for c in ("LANES", "MAX_SPD", "ROAD_RANK"):
            links[c] = pd.to_numeric(links[c], errors="coerce")
        ov = gpd.overlay(links[["LINK_ID", "LANES", "MAX_SPD", "ROAD_RANK", "geometry"]], cells[["cid", "geometry"]], how="intersection", keep_geom_type=True)
        ov["len"] = ov.geometry.length
        g_ = ov.groupby("cid")
        src = "성남_링크(표준노드링크 2026-09-14)"
        add_col(S, "CTX_링크수", "맥락", g_["LINK_ID"].nunique(), "칸과 겹치는 표준 링크 수", src, "겹치는 링크의 고유 개수", "2026-09", "방향별로 두 줄이라 실제 도로 수보다 많음, 골목은 일부만 포함")
        add_col(S, "CTX_링크연장_m", "맥락", g_["len"].sum().round(1), "칸 안에 들어온 링크 길이 합", src, "칸 경계로 자른 링크 길이의 합", "2026-09", "방향별 두 줄이라 도로 길이의 약 2배일 수 있음 — 도로 총연장으로 쓰지 않기")
        walk = ov[~ov["ROAD_RANK"].isin([101, 102])]
        add_col(S, "CTX_보행분석_링크연장_m", "맥락", walk.groupby("cid")["len"].sum().round(1), "도로등급 101·102(고속도로) 제외 링크 길이", src, "고속도로 제외 후 길이 합", "2026-09", "보행자가 다닐 수 없는 도로를 뺀 값")
        add_col(S, "CTX_평균차로수", "맥락", g_["LANES"].mean().round(2), "칸 링크의 평균 차로수", src, "링크 평균", "2026-09", "링크 수가 적은 칸은 값이 불안정")
        add_col(S, "CTX_최대차로수", "맥락", g_["LANES"].max(), "칸 링크의 최대 차로수", src, "링크 최대", "2026-09", "")
        add_col(S, "CTX_최대제한속도", "맥락", g_["MAX_SPD"].max(), "칸 링크의 최대 제한속도(km/h)", src, "링크 최대", "2026-09", "규제 속도이지 실제 통행속도가 아님")
        low = ov.assign(l30=(ov["MAX_SPD"] <= 30)).groupby("cid")["l30"].mean() * 100
        add_col(S, "CTX_30이하_링크비율", "맥락", low.round(1), "제한속도 30km/h 이하 링크의 비율(%)", src, "링크 수 기준", "2026-09", "생활도로 속도 하향 구간 정도")
        add_col(S, "CTX_고속도로등급_링크수", "맥락", ov[ov["ROAD_RANK"].isin([101, 102])].groupby("cid")["LINK_ID"].nunique(), "도로등급 101·102 링크 수", src, "개수", "2026-09", "보행 분석에서 제외 대상")
        S[["CTX_링크수", "CTX_링크연장_m", "CTX_보행분석_링크연장_m", "CTX_고속도로등급_링크수"]] = S[["CTX_링크수", "CTX_링크연장_m", "CTX_보행분석_링크연장_m", "CTX_고속도로등급_링크수"]].fillna(0)
        qa("성남_링크", len(links), len(links), int(ov["LINK_ID"].nunique()))
    if np_ is not None:
        nodes = gpd.read_file(np_, encoding="cp949").to_crs(CRS_M)
        n101 = nodes[pd.to_numeric(nodes["NODE_TYPE"], errors="coerce") == 101]
        n = count_points(S, n101, "CTX_교차로수", "맥락", "교차로(NODE_TYPE 101) 수", "성남_노드", "2026-09", "NODE_TYPE 102~107은 교차로가 아님(시작·끝점·속성변화점·교량·행정경계·IC·보조점, 코드 뜻은 추정)")
        tp = nodes[pd.to_numeric(nodes["TURN_P"], errors="coerce") == 1]
        count_points(S, tp, "CTX_회전제한_노드수", "맥락", "회전 제한 정보가 있는 노드(TURN_P=1) 수", "성남_노드", "2026-09", "회전 제한 상세(TURNINFO)는 포함하지 않음")
        qa("성남_노드(교차로 101)", len(nodes), len(n101), n)

    # ---- 구·행정동
    S["ID_구"], S["ID_행정동"], S["ID_행정동코드"], S["ID_구동출처"] = None, None, None, None
    dongp = first(["dong"], (".shp",), exclude=("성남",)) or first(["행정동"], (".shp",))
    dong = None
    if dongp is not None:
        try:
            d = read_shp_auto(dongp)
            if d.crs is None: d = d.set_crs(CRS_M)
            d = d.to_crs(CRS_M)
            cc = next((c for c in d.columns if c.upper() in ("ADM_CD", "ADM_DR_CD")), None)
            nc = next((c for c in d.columns if c.upper() in ("ADM_NM", "ADM_DR_NM")), None)
            if cc and nc:
                d = d[d[cc].astype(str).str.startswith(("31021", "31022", "31023"))].copy()
                if len(d):
                    d["코드"], d["이름"] = d[cc].astype(str), d[nc].astype(str)
                    d["구"] = d["코드"].str[:5].map({"31021": "성남시 수정구", "31022": "성남시 중원구", "31023": "성남시 분당구"})
                    dong = d[["코드", "이름", "구", "geometry"]]
        except Exception as e:
            print("행정동 경계를 읽지 못했습니다:", str(e)[:80])
    cp = gpd.GeoDataFrame({"cid": cells["cid"]}, geometry=cells.geometry.centroid, crs=CRS_M)
    if dong is not None:
        j = gpd.sjoin(cp, dong, how="left", predicate="within"); j = j[~j.index.duplicated()].set_index("cid")
        S["ID_구"], S["ID_행정동"], S["ID_행정동코드"] = j["구"], j["이름"], j["코드"]
        S.loc[S["ID_구"].notna(), "ID_구동출처"] = "SGIS 행정동 경계"
    miss = S["ID_구"].isna()
    if miss.any() and links is not None and "구" in links.columns:
        sel = cp[cp["cid"].isin(S.index[miss])]
        nn = gpd.sjoin_nearest(sel, links[["구", "행정동", "geometry"]], how="left", max_distance=800)
        nn = nn[~nn.index.duplicated()].set_index("cid")
        S.loc[nn.index, "ID_구"], S.loc[nn.index, "ID_행정동"] = nn["구"], nn["행정동"]
        S.loc[nn.index[nn["구"].notna()], "ID_구동출처"] = "가까운 링크로 추정(800m 이내)"
    _nm = S["ID_행정동"].dropna().astype(str)
    if len(_nm) and _nm.str.contains(r"(?:동|읍|면|가|리)$").mean() < 0.9:
        print("⚠️ 행정동 이름이 깨져 있을 수 있습니다(글자 인코딩 문제). 01_공간기준의 행정동 경계 파일을 확인하세요.")
    DOC.append(dict(컬럼="ID_구 / ID_행정동 / ID_행정동코드 / ID_구동출처", 역할="식별", 의미="칸이 속한 구·행정동", 출처="SGIS 행정동 경계(있으면) 또는 성남_링크의 구·행정동", 집계방법="칸 중심점이 들어간 경계, 없으면 800m 이내 가까운 링크", 기준시점="2025Q2/2026-09", 주의="링크 추정은 경계 기준과 구 98%·행정동 91% 일치. 행정동코드는 SGIS 경계가 있을 때만 채워짐"))

    # ---- 경사·표고
    try:
        import rasterio
        def rast(p, nm):
            with rasterio.open(p) as r:
                a = r.read(1, masked=True).astype("float64")
                rr, cc_ = np.indices(a.shape)
                xs, ys = rasterio.transform.xy(r.transform, rr.ravel(), cc_.ravel(), offset="center")
            v = np.ma.filled(a.ravel(), np.nan)
            cid = pd.Series([f"{int(np.floor(x / CELL))}_{int(np.floor(y / CELL))}" for x, y in zip(xs, ys)])
            return pd.DataFrame({"cid": cid, "v": v}).dropna()
        sp = first(["slope"], (".tif",))
        if sp is not None:
            d = rast(sp, "slope"); g_ = d.groupby("cid")["v"]
            add_col(S, "COND_경사_평균_도", "위험 조건", g_.mean().round(2), "칸 안 경사도 평균(°)", "slope_37709.tif(DEM 90m에서 계산)", "칸 안 90m 셀 중심의 평균", "DEM 2025", "90m 셀이라 보도·골목 경사나 단차는 못 봄 — 오르막 동네 후보용. 가장자리 일부는 비어 있음")
            add_col(S, "COND_경사_최대_도", "위험 조건", g_.max().round(2), "칸 안 경사도 최대(°)", "slope_37709.tif", "칸 안 90m 셀의 최대", "DEM 2025", "")
            qa("slope_37709.tif", int(1), int(len(d)), int(d["cid"].isin(S.index).sum()), "90m 셀 수")
        dp = first(["37709"], (".img",), aux=True)
        if dp is not None:
            d = rast(dp, "dem"); g_ = d.groupby("cid")["v"]
            add_col(S, "CTX_표고_평균_m", "맥락", g_.mean().round(1), "칸 안 표고 평균(m)", "(DEM원본)37709.img", "칸 안 90m 셀 평균", "DEM 2025", "저지대(침수) 후보 확인용")
            add_col(S, "CTX_표고_최저_m", "맥락", g_.min().round(1), "칸 안 표고 최저(m)", "(DEM원본)37709.img", "칸 안 90m 셀 최저", "DEM 2025", "")
    except Exception as e:
        print("경사·표고를 건너뜁니다:", str(e)[:100])

    # ---- 조도·휘도
    p = first(["조도", "휘도", "데이터"], (".csv",))
    if p is not None:
        d = read_any(p); n0 = len(d)
        g = points_df(d)
        il = pick(d.columns, ["조도(ILLUMINATION)", "조도"])
        g["조도"] = to_num(d.loc[g.index, il]); g = g.drop_duplicates(subset=[c for c in d.columns]).dropna(subset=["조도"])
        c = cid_of(g)
        add_col(S, "COND_조도_측정수", "위험 조건", c.value_counts().rename("n"), "칸 안 야간 조도 측정점 수", p.name, "정제 후 측정점 개수", "2022", "정제: 좌표 오류·완전 중복·결측 제외(39,794점). 이동 측정이라 도로 위 값")
        S["COND_조도_측정수"] = S["COND_조도_측정수"].fillna(0)
        add_col(S, "COND_조도_평균", "위험 조건", g["조도"].groupby(c).mean().round(2), "칸 안 조도 평균", p.name, "측정점 평균", "2022", "단위 미표기(lux 추정). 절대 임계값 금지 — 상대 비교(백분위)로만")
        add_col(S, "COND_조도_최소", "위험 조건", g["조도"].groupby(c).min().round(2), "칸 안 조도 최소", p.name, "측정점 최소", "2022", "측정점이 적은 칸(5개 미만)은 불안정")
        qa(p.name, n0, len(g), int(c.isin(S.index).sum()), "정제 후")

    # ---- 횡단보도
    p = first(["횡단보도"], (".csv",), exclude=("험프",))
    if p is not None:
        d = read_any(p); g = points_df(d); c = cid_of(g)
        y = lambda col, v: (g[col].fillna("") == v)
        n = count_points(S, g, "COND_횡단보도_수", "위험 조건", "칸 안 횡단보도 수", p.name, "제출 시점", "성남 전체가 아니라 제출된 691곳(대로 위주)")
        for nm, col, v, mean in (("COND_횡단보도_신호없음_수", "보행자신호등유무", "N", "보행자 신호등이 없는(N) 횡단보도"), ("COND_횡단보도_점자블록없음_수", "점자블록유무", "N", "점자블록이 없는(N) 횡단보도"), ("COND_횡단보도_턱낮춤_수", "보도턱낮춤여부", "Y", "보도턱 낮춤이 있는(Y) 횡단보도")):
            if col in g.columns:
                count_points(S, g[y(col, v)], nm, "위험 조건", f"칸 안 {mean} 수", p.name, "제출 시점", "빈칸은 '없음'이 아니라 입력 안 됨일 수 있음(턱낮춤은 분당 위주 입력)")
        for nm, col in (("COND_횡단보도_평균폭_m", "횡단보도폭"), ("COND_횡단보도_평균연장_m", "횡단보도연장")):
            if col in g.columns:
                add_col(S, nm, "위험 조건", to_num(g[col]).groupby(c).mean().round(1), f"칸 안 횡단보도 {col} 평균(m)", p.name, "평균", "제출 시점", "")
        qa(p.name, len(d), len(g), n)

    # ---- 우회전 사각지대·적치물·전용도로
    p = first(["우회전", "사각지대"], (".txt", ".json"))
    if p is not None:
        d = read_json_records(p); g = points_df(d)
        n = count_points(S, g, "COND_사각지대_수", "위험 조건", "칸 안 우회전 사각지대 수", p.name, "2022-10~11", "현재 시야 가림 상태가 아님(2022 시점)")
        qa(p.name, len(d), len(g), n)
    p = first(["적치물"], (".txt", ".json"))
    if p is not None:
        d = read_json_records(p); g = points_df(d)
        n = count_points(S, g, "COND_적치물_수", "위험 조건", "칸 안 적치물 등 장애물 수", p.name, "2022-09~10", "보행자 전용도로 안에서만 조사 — 일반 보도 현황이 아님")
        qa(p.name, len(d), len(g), n)
    p = first(["전용도로"], (".json", ".txt"))
    if p is not None:
        d = read_json_records(p)
        la = (to_num(d["보행자전용도로시작점위도"]) + to_num(d["보행자전용도로종료점위도"])) / 2
        lo = (to_num(d["보행자전용도로시작점경도"]) + to_num(d["보행자전용도로종료점경도"])) / 2
        d2 = d.assign(위도=la, 경도=lo); g = points_df(d2); c = cid_of(g)
        n = count_points(S, g, "COND_전용도로_수", "위험 조건", "칸 안 보행자 전용도로 수(시작·끝점 중간 기준)", p.name, "2022", "전용도로 한정·분당 편중. 점검결과 전부 '합격'이라 변별력 없음")
        add_col(S, "COND_전용도로_평균폭_m", "위험 조건", to_num(g["보행자전용도로폭"]).groupby(c).mean().round(1), "칸 안 전용도로 폭 평균(m)", p.name, "평균", "2022", "")
        qa(p.name, len(d), len(g), n)

    # ---- 단속
    p = first(["CCTV별", "단속건수"], (".csv",))
    if p is not None:
        d = read_any(p); g = points_df(d); g["건"] = to_num(d.loc[g.index, "단속건수"]).fillna(0)
        n = count_points(S, g, "COND_단속_CCTV수", "위험 조건", "칸 안 불법주정차 단속 CCTV 수", p.name, "2024-11~2025-12", "단속건수≠위험도. 연결률 분당 90.7·수정 69.5·중원 46.0%라 원도심 과소평가")
        count_points(S, g, "COND_단속_연간건수", "위험 조건", "칸 안 CCTV에 연결된 연간 단속건수 합", p.name, "2024-11~2025-12", "연결 안 된 CCTV(125대)는 0이 아니라 연결 없음. 고정형 CCTV 단속만(전체의 35%)", value=g["건"], how="단속건수 합")
        qa(p.name, len(d), len(g), n)

    # ---- 보안등(있으면)
    p = first(["보안등"], (".csv", ".xlsx", ".txt"), exclude=("표준", "컬럼", "정의"))
    if p is not None:
        try:
            d = read_any(p) if p.suffix.lower() in (".csv", ".txt") else pd.read_excel(p, dtype=str)
            g = points_df(d); cnt = pick(d.columns, ["설치개수", "개수"])
            n = count_points(S, g, "COND_보안등_수", "위험 조건", "칸 안 보안등 위치 수", p.name, "파일 기준일", "설치개수≠점등 상태. 고장·소등 여부는 알 수 없음")
            if cnt:
                count_points(S, g, "COND_보안등_설치개수", "위험 조건", "칸 안 보안등 설치개수 합", p.name, "파일 기준일", "한 위치에 여러 개가 있을 수 있음", value=to_num(d.loc[g.index, cnt]).fillna(1), how="설치개수 합")
            qa(p.name, len(d), len(g), n)
        except Exception as e:
            print("보안등을 읽지 못했습니다:", str(e)[:80])
    else:
        for nm in ("COND_보안등_수", "COND_보안등_설치개수"):
            S[nm] = np.nan
            DOC.append(dict(컬럼=nm, 역할="위험 조건", 의미="칸 안 보안등(수 / 설치개수 합)", 출처="성남시 보안등 9,639개(센아 확보, 이 실행에는 파일이 없음)", 집계방법="03_보행환경시설에 두면 채워짐", 기준시점="", 주의="설치개수≠점등 상태"))

    # ---- 노출: 정류소
    p = first(["정류소", "승하차", "좌표"], (".csv",))
    if p is not None:
        d = read_any(p); g = points_df(d)
        n = count_points(S, g, "EXP_정류소수", "노출", "칸 안 버스 정류소 수", p.name, "2026-03", "좌표 1,121곳이 2018 정류소 현황 기준 — 신규·이전 정류소 위치 오차 가능")
        for nm, col in (("EXP_승차_일평균", "승차합계"), ("EXP_하차_일평균", "하차"), ("EXP_승하차_일평균", "승하차")):
            count_points(S, g, nm, "노출", f"칸 안 정류소 {col} 일평균 합", p.name, "2026-03", "승하차량 자체가 위험도는 아님 — 보행 노출 대용. 시간대 없음", value=to_num(d.loc[g.index, col]).fillna(0), how="합")
        qa(p.name, len(d), len(g), n)

    # ---- 취약 이용자
    p = first(["어린이집", "유치원", "통합", "최종"], (".csv",))
    if p is not None:
        d = read_any(p); d = d[d["확인상태"] != "카카오만(유치원 아님 의심)"]; g = points_df(d)
        for nm, t in (("VUL_어린이집수", "어린이집"), ("VUL_유치원수", "유치원")):
            n = count_points(S, g[g["유형"] == t], nm, "취약", f"칸 안 {t} 수", p.name, "2026", "'운영 미확인' 5곳 포함('유치원 아님 의심' 4곳은 제외). 시설 수≠이용자 수")
        qa(p.name, len(d), len(g), n, "유치원 아님 의심 제외")
    p = first(["노인의료복지시설"], (".csv",))
    if p is not None:
        d = read_any(p); g = points_df(d)
        nmc = pick(d.columns, ["시설명", "기관명", "명칭"])
        key = [c for c in g.columns if ("시설명" in c or "명칭" in c)] or [c for c in g.columns if "도로명" in c]
        g = g.drop_duplicates(subset=key) if key else g   # 같은 시설이 2줄씩 있어 시설명이 같은 줄을 하나로 합침(지번 주소 표기만 다른 경우 포함)
        n = count_points(S, g, "VUL_노인의료복지시설수", "취약", "칸 안 노인의료복지시설 수", p.name, "2022 전후", "한 시설이 2줄씩 있어 시설명이 같은 줄을 하나로 합침(84줄→42곳)")
        qa(p.name, len(d), len(g), n, "중복 제거")
    p = first(["경로당"], (".csv",))
    if p is not None:
        d = read_any(p)
        st = pick(d.columns, ["영업상태명", "운영상태", "상세영업상태명"])
        if st: d = d[d[st].astype(str).str.contains("운영|영업")]
        g = points_df(d)
        n = count_points(S, g, "VUL_경로당수", "취약", "칸 안 경로당 수(운영 중, 좌표 있는 곳)", p.name, "인허가 자료", "좌표가 없는 곳(약 26%)은 빠짐")
        qa(p.name, len(d), len(g), n, "운영 중만")
    gg = []
    for pat in (["장애유형별", "거주시설"], ["장애인관련시설"]):
        p = first(pat, (".csv",), exclude=("집계",))
        if p is not None:
            gg.append(points_df(read_any(p)))
    gg = [x for x in gg if x is not None and len(x)]
    if gg:
        g = pd.concat(gg); n = count_points(S, g, "VUL_장애인시설수", "취약", "칸 안 장애인 거주·관련 시설 수(성남 7곳)", "장애유형별거주시설현황 + 장애인관련시설현황(2)", "2022 전후", "성남 7곳뿐")
        qa("장애인 시설 2종", len(g), len(g), n)
    # 보호구역 (경찰청 현행 폴리곤)
    fs = find_files(["경찰청", "보호구역"], (".txt", ".json"))
    if fs:
        from pyproj import Transformer
        recs = []
        for f in fs:
            for r in read_json_records(f).to_dict("records"):
                try: recs.append((r["ptznMngNo"], str(r["fcltTypeCd"]), wkt.loads(r["fturGeomVl"])))
                except Exception: pass
        pz = gpd.GeoDataFrame({"zone": [r[0] for r in recs], "type": [r[1] for r in recs]}, geometry=[r[2] for r in recs], crs=5181).to_crs(CRS_M)
        j = gpd.sjoin(cells[["cid", "geometry"]], pz, predicate="intersects")
        for nm, tc, lab in (("VUL_보호구역_어린이", "1", "어린이"), ("VUL_보호구역_노인", "2", "노인"), ("VUL_보호구역_장애인", "3", "장애인")):
            S[nm] = j[j["type"] == tc].groupby("cid")["zone"].nunique().reindex(S.index).fillna(0)
            DOC.append(dict(컬럼=nm, 역할="취약", 의미=f"칸과 겹치는 {lab}보호구역 수", 출처="경찰청_전국_보호구역 현황(현행 206곳)", 집계방법="폴리곤이 칸과 겹치는 보호구역의 고유 개수", 기준시점="2025~2026", 주의="구역 모양이 칸보다 커서 한 보호구역이 여러 칸에 들어감"))
        S["VUL_보호구역_합"] = j.groupby("cid")["zone"].nunique().reindex(S.index).fillna(0)
        DOC.append(dict(컬럼="VUL_보호구역_합", 역할="취약", 의미="칸과 겹치는 보호구역 수(전체)", 출처="경찰청_전국_보호구역 현황", 집계방법="고유 개수", 기준시점="2025~2026", 주의="2022 마스터가 아니라 현행 기준"))
        qa("경찰청 보호구역", len(pz), len(pz), int(j["zone"].nunique()))
    # SGIS 연령 구성 (행정동코드가 있을 때)
    ap, tp_ = first(["성연령별인구"], (".csv",)), first(["인구총괄", "총인구"], (".csv",))
    S["VUL_동_총인구"], S["VUL_동_65세이상비율"], S["VUL_동_0_9세비율"] = np.nan, np.nan, np.nan
    if ap is not None and tp_ is not None and S["ID_행정동코드"].notna().any():
        a = pd.read_csv(ap, encoding="cp949", dtype=str); a["v"] = pd.to_numeric(a["통계값"], errors="coerce")
        t = pd.read_csv(tp_, encoding="cp949", dtype=str); t["v"] = pd.to_numeric(t["통계값"], errors="coerce")
        W = a[a["행정구역코드"].str.len() == 8].pivot(index="행정구역코드", columns="통계항목", values="v")
        T = t[(t["행정구역코드"].str.len() == 8) & (t["통계항목"] == "to_in_001")].set_index("행정구역코드")["v"]
        old = W[[f"in_age_{i:03d}" for i in range(14, 22)]].sum(axis=1, min_count=1)
        kid = W[[f"in_age_{i:03d}" for i in (1, 2)]].sum(axis=1, min_count=1)
        S["VUL_동_총인구"] = S["ID_행정동코드"].map(T)
        S["VUL_동_65세이상비율"] = S["ID_행정동코드"].map((old / T * 100).round(2))
        S["VUL_동_0_9세비율"] = S["ID_행정동코드"].map((kid / T * 100).round(2))
    for nm, mean in (("VUL_동_총인구", "행정동 총인구"), ("VUL_동_65세이상비율", "행정동 65세 이상 비율(%)"), ("VUL_동_0_9세비율", "행정동 0~9세 비율(%)")):
        DOC.append(dict(컬럼=nm, 역할="취약", 의미=mean, 출처="SGIS 2025년 기준(2024) 성연령별인구·총인구", 집계방법="칸이 속한 행정동의 값(칸마다 같은 값이 반복됨)", 기준시점="2024", 주의="행정동 경계(ADM_CD)가 있을 때만 채워짐. 비율의 분모는 총인구 파일, 비밀보호 빈 값 6%"))

    # ---- 사고 결과
    p = first(["사망", "교통사고"], (".csv",))
    if p is not None:
        d = read_any(p); g = points_df(d, "WGS84위도", "WGS84경도")
        ped = (g["사고유형_대분류"] == "차대사람") | (g["피해자 당사자 종별"] == "보행자")
        n = count_points(S, g, "RES_사망사고수", "사고 결과", "칸 안 사망사고 수(전체)", p.name, "2012~2022", "2023~2025는 위치가 없음. 다발지와 사망자 수를 더하면 중복")
        count_points(S, g[ped], "RES_보행사망사고수", "사고 결과", "칸 안 보행자 관련 사망사고 수", p.name, "2012~2022", "차대사람 또는 피해자가 보행자인 사고")
        count_points(S, g[ped & (g["사고유형"] == "횡단중")], "RES_보행사망_횡단중", "사고 결과", "칸 안 보행 사망사고 중 횡단중", p.name, "2012~2022", "")
        count_points(S, g[ped & g["주야구분명"].astype(str).str.contains("야")], "RES_보행사망_야간", "사고 결과", "칸 안 보행 사망사고 중 야간", p.name, "2012~2022", "")
        count_points(S, g, "RES_사망자수", "사고 결과", "칸 안 사망자 수 합", p.name, "2012~2022", "한 사고에 여러 명 사망 가능", value=to_num(g["사망자수"]).fillna(0), how="사망자수 합")
        qa(p.name, len(d), len(g), n)
    fs = find_files(["사고위험지역"], (".txt", ".json"))
    fs = [f for f in fs if "2022" in f.name and "2025" in f.name] or fs
    if fs:
        geoms, yrs = [], []
        for f in fs:
            for r in read_json_records(f).to_dict("records"):
                m = re.search(r"(\d{4})년도", str(r.get("acc_risk_area_nm", "")))
                if r.get("geom_wkt") and m:
                    geoms.append(wkt.loads(r["geom_wkt"])); yrs.append(int(m.group(1)))
        rk = gpd.GeoDataFrame({"year": yrs}, geometry=geoms, crs=CRS_M)
        j = gpd.sjoin(cells[["cid", "geometry"]], rk, predicate="intersects")
        S["RES_위험지역_연수"] = j.groupby("cid")["year"].nunique().reindex(S.index).fillna(0)
        S["RES_위험지역_최근연도"] = j.groupby("cid")["year"].max().reindex(S.index)
        DOC.append(dict(컬럼="RES_위험지역_연수", 역할="사고 결과", 의미="칸과 겹치는 사고위험지역이 있었던 연도 수(0~4)", 출처="사고위험지역정보 2022~2025(3개)", 집계방법="연도의 고유 개수", 기준시점="2022~2025", 주의="차대차 중심이라 보행 신호로는 약함. 구·연도별 선정 기준이 달라 개수 비교 금지"))
        DOC.append(dict(컬럼="RES_위험지역_최근연도", 역할="사고 결과", 의미="그 칸에 위험지역이 마지막으로 나온 연도", 출처="사고위험지역정보", 집계방법="최대 연도", 기준시점="2022~2025", 주의=""))
        qa("사고위험지역 면", len(rk), len(rk), int(j.index.nunique()))
    p = first(["사고다발지", "6유형"], (".csv",), exclude=("표준",)) or first(["사고다발지"], (".csv",), exclude=("표준", "현황"))
    if p is not None:
        d = read_any(p)
        def poly(t):
            m = re.findall(r"\[\s*([0-9.]+),\s*([0-9.]+)\s*\]", str(t)); return Polygon([(float(a), float(b)) for a, b in m]) if len(m) >= 3 else None
        pg = [poly(t) for t in d["사고다발지역폴리곤정보"]]; ok = [x is not None for x in pg]
        dd = d[ok].copy(); dd["유형"] = dd["사고유형구분"].astype(str).str.replace(r"보행어\?.*", "보행어린이사고다발지", regex=True); dd["연도"] = to_num(dd["사고년도"])
        mp = gpd.GeoDataFrame(dd, geometry=[x for x in pg if x is not None], crs=4326).to_crs(CRS_M)
        j = gpd.sjoin(cells[["cid", "geometry"]], mp[["유형", "연도", "geometry"]], predicate="intersects")
        S["RES_다발지_수"] = j.groupby("cid").size().reindex(S.index).fillna(0)
        DOC.append(dict(컬럼="RES_다발지_수", 역할="사고 결과", 의미="칸과 겹치는 사고다발지 행 수(연도·유형별 행)", 출처=p.name, 집계방법="겹치는 행의 개수", 기준시점="2012~2025", 주의="같은 장소가 연도마다 반복되므로 '건수'가 아니라 '반복 정도'. 연도 간 개수 비교 금지(2025 보행노인 급증)"))
        for nm, t in (("RES_다발지_보행노인", "보행노인사고다발지"), ("RES_다발지_무단횡단", "무단횡단사고다발지"), ("RES_다발지_자전거", "자전거사고다발지"), ("RES_다발지_보행어린이", "보행어린이사고다발지"), ("RES_다발지_스쿨존", "스쿨존내어린이사고다발지")):
            S[nm] = j[j["유형"] == t].groupby("cid").size().reindex(S.index).fillna(0)
            DOC.append(dict(컬럼=nm, 역할="사고 결과", 의미=f"칸과 겹치는 {t[:-5]} 다발지 행 수", 출처=p.name, 집계방법="유형별 겹치는 행 수", 기준시점="2012~2025", 주의="식별자가 중복이라 장소 키로 쓰지 않음"))
        S["RES_다발지_최근4년수"] = j[j["연도"] >= 2022].groupby("cid").size().reindex(S.index).fillna(0)
        DOC.append(dict(컬럼="RES_다발지_최근4년수", 역할="사고 결과", 의미="2022~2025년 다발지 행 수", 출처=p.name, 집계방법="연도 2022 이상", 기준시점="2022~2025", 주의=""))
        qa(p.name, len(d), len(mp), int(j.index.nunique()))

    # ---- 보행자 사망·중상 다발지 (행정안전부 교통약자교통사고다발지_보행자, 2023 묶음으로 보임)
    p = first(["교통약자", "다발지", "보행자"], (".csv",))
    if p is not None:
        d0 = read_any(p)
        d = d0[d0["STDG_CD"].astype(str).str.startswith(("41131", "41133", "41135"))].copy()   # 성남시만(법정동코드 앞 5자리)
        hp = gpd.GeoDataFrame(d, geometry=[shape(json.loads(t)) for t in d["MLPL_RGN_PLGN"]], crs=4326).to_crs(CRS_M)
        for c_ in ("ACDNT_NOCS", "DCSD_CNT", "SWPR_CNT", "LAT", "LOT"):
            hp[c_] = to_num(hp[c_])
        j = gpd.sjoin(cells[["cid", "geometry"]], hp[["BRNCH_CD", "geometry"]], predicate="intersects")
        S["RES_보행자다발지_수"] = j.groupby("cid")["BRNCH_CD"].nunique().reindex(S.index).fillna(0)
        DOC.append(dict(컬럼="RES_보행자다발지_수", 역할="사고 결과", 의미="칸과 겹치는 보행자 사망·중상 다발지 지점 수", 출처=p.name, 집계방법="반경 약 82m 원이 칸과 겹치는 지점의 고유 개수", 기준시점="2023(묶음 ID 2023060)", 주의="한 지점이 인접한 여러 칸에 걸쳐 중복으로 잡힘. 6유형 다발지(반경 79~300m)와 정의가 달라 개수를 서로 비교·합산 금지"))
        pt = gpd.GeoDataFrame(hp.drop(columns="geometry"), geometry=gpd.points_from_xy(hp["LOT"], hp["LAT"], crs=4326)).to_crs(CRS_M)
        n = count_points(S, pt, "RES_보행자다발지_사고건수", "사고 결과", "지점 중심이 칸 안에 있는 다발지의 사고 건수 합", p.name, "2023(묶음 ID 2023060)", "중심점 기준이라 중복 없음(전 칸 합 = 전체). 사망점·6유형과 같은 사고가 겹칠 수 있어 더하지 않기", value=pt["ACDNT_NOCS"], how="사고건수 합")
        count_points(S, pt, "RES_보행자다발지_사망자수", "사고 결과", "지점 중심이 칸 안에 있는 다발지의 사망자 수 합", p.name, "2023(묶음 ID 2023060)", "중심점 기준, 사망점(2012~2022)과 같은 사고가 겹칠 수 있음", value=pt["DCSD_CNT"], how="사망자수 합")
        count_points(S, pt, "RES_보행자다발지_중상자수", "사고 결과", "지점 중심이 칸 안에 있는 다발지의 중상자 수 합", p.name, "2023(묶음 ID 2023060)", "비사망 보행사고의 위치 신호. 중심점 기준, 칸 합 = 전체", value=pt["SWPR_CNT"], how="중상자수 합")
        qa(p.name, len(d0), len(d), int(j["BRNCH_CD"].nunique()), "성남시만(울산 중구 성남동 등 제외)")

    # ---- 완화·안전시설 (99_보조_검증자료)
    MIT = [("MIT_과속방지턱수", ["과속방지턱", "현황"], (".csv",), ("컬럼", "정보"), "과속방지턱", "속도 저감 시설 — 위험요인이 아니라 완화시설, 개수 가산 금지. 높이 단위 혼재"),
           ("MIT_단속카메라수", ["교통단속", "카메라"], (".csv",), (), "교통단속 카메라", "보호구역 안 시설 위주(112곳)"),
           ("MIT_울타리수", ["울타리"], (".csv",), (), "울타리·무단횡단 방지펜스", "보호구역 안에서만 조사(128곳)"),
           ("MIT_안전표지수", ["도로안전표지"], (".csv",), (), "도로안전표지", "일부(695개)만 포함 — 존재만, 상태·가독성은 알 수 없음"),
           ("MIT_생활안전CCTV수", ["생활안전", "cctv"], (".csv",), (), "생활안전 CCTV", "많다고 보행 위험이 높다는 뜻이 아님 — 점수에서 제외 대상"),
           ("MIT_신호등수", ["신호등"], (".csv",), ("교통신호기", "시설물", "잔여"), "신호등(차량 신호 위주)", "보행자 녹색시간은 없음 — 임의 해석 금지"),
           ("MIT_적색표면수", ["도로적색표면"], (".txt", ".json"), (), "도로 적색표면(보호구역)", "2022·보호구역 안만, 현행에 없는 보호구역 35점 포함")]
    for nm, pat, ex, exc, lab, cau in MIT:
        p = first(pat, ex, exclude=exc, aux=True)
        if p is None:
            S[nm] = np.nan; DOC.append(dict(컬럼=nm, 역할="완화·안전시설", 의미=f"칸 안 {lab} 수", 출처="(파일 없음 — 비어 있음)", 집계방법="점 개수", 기준시점="", 주의=cau)); continue
        d = read_json_records(p) if ex[0] == ".txt" else read_any(p)
        g = points_df(d)
        if g is None:
            continue
        n = count_points(S, g, nm, "완화·안전시설", f"칸 안 {lab} 수", p.name, "파일 기준일", cau)
        qa(p.name, len(d), len(g), n)
    p = first(["옐로우", "카펫"], (".txt", ".json"), aux=True)
    if p is not None:
        d = read_json_records(p); g = points_df(d)
        n = count_points(S, g, "MIT_옐로카펫수", "완화·안전시설", "칸 안 옐로우 카펫 수", p.name, "2022", "2022·보호구역 안만 조사")
        qa(p.name, len(d), len(g), n)

    # ---- 정리·저장
    order = [c for c in S.columns]
    S = S.reset_index(drop=True)
    pref = ["ID_", "CTX_", "RES_", "COND_", "EXP_", "VUL_", "MIT_"]
    S = S[sorted(S.columns, key=lambda c: (next((i for i, p_ in enumerate(pref) if c.startswith(p_)), 9), order.index(c) if c in order else 0))]
    OUT.mkdir(parents=True, exist_ok=True)
    S.to_csv(OUT / "RADAR_격자테이블_250m.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(DOC).to_csv(OUT / "RADAR_격자테이블_컬럼설명.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(QA).to_csv(OUT / "RADAR_격자테이블_점검표.csv", index=False, encoding="utf-8-sig")
    print(f"\n저장: output/RADAR_격자테이블_250m.csv ({len(S):,}칸 × {len(S.columns)}열)")
    return S


if __name__ == "__main__":
    main()