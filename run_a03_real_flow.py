"""A-03/A-04/A-05 실제 가공 CSV 로컬 연결 검토.
프로젝트 루트에서 uv run python run_a03_real_flow.py
입력 inputs/a03_real의 지정된 8개 CSV. 출력 outputs/a03_flow/<실행번호>.
팀 서버 업로드, 운영 DB 저장, 팀 로그인, A-06 공간 검사는 포함하지 않습니다.
"""
import csv
import hashlib
import io
import json
import re
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path
from uuid import uuid4

PROFILES = [{'file': '17_src_lux_point.csv', 'data_id': 'DAT-28', 'source_id': 'SRC21', 'name': '도로 조도·휘도', 'basis_column': 'measure_date', 'basis_kind': 'date', 'columns': ['src_id', 'gid', 'measure_date', 'measure_time', 'lat', 'lon', 'illuminance', 'luminance', 'lunar_phase', 'raw_file'], 'key': 'src_id', 'numeric': ['lat', 'lon', 'illuminance', 'luminance']}, {'file': '19_src_blind_spot.csv', 'data_id': 'DAT-24', 'source_id': 'SRC13', 'name': '우회전 사각지대', 'basis_column': 'referencedate', 'basis_kind': 'date', 'columns': ['src_id', 'gid', 'id', 'idprt', 'ctprvnnm', 'signgunm', 'emdnm', 'lnmadr', 'crslkmanageno', 'deloc', 'latitude', 'longitude', 'referencedate', 'image', 'remark', 'raw_file'], 'key': 'src_id', 'numeric': ['latitude', 'longitude']}, {'file': '20_src_obstacle.csv', 'data_id': 'DAT-23', 'source_id': 'SRC15', 'name': '적치물 등 장애물', 'basis_column': 'referencedate', 'basis_kind': 'date', 'columns': ['src_id', 'gid', 'id', 'latitude', 'longitude', 'itlpc', 'ctprvnnm', 'signgunm', 'deloc', 'referencedate', 'image', 'remark', 'raw_file'], 'key': 'src_id', 'numeric': ['latitude', 'longitude']}, {'file': '36_src_red_surface.csv', 'data_id': 'DAT-26', 'source_id': 'SRC22', 'name': '도로 적색표면', 'basis_column': 'referencedate', 'basis_kind': 'date', 'columns': ['src_id', 'gid', 'id', 'latitude', 'longitude', 'sfznid', 'ctprvnnm', 'signgunm', 'sisulnm', 'policenm', 'referencedate', 'image', 'remark', 'raw_file'], 'key': 'src_id', 'numeric': ['latitude', 'longitude']}, {'file': '39_src_ped_hotspot_5y.csv', 'data_id': 'DAT-02', 'source_id': 'SRC37', 'name': 'TAAS 보행자 교통사고 다발지역', 'basis_column': 'ref_year', 'basis_kind': 'short_year', 'columns': ['row_id', 'ref_year', 'gu', 'legal_dong', 'spot_name', 'accident_cnt', 'casualty_cnt', 'death_cnt', 'serious_injury_cnt', 'minor_injury_cnt', 'injury_report_cnt', 'repeat_cnt_21_25', 'lat', 'lon', 'coord_source', 'admin_dong_name', 'grid_no', 'gid'], 'key': 'row_id', 'numeric': ['accident_cnt', 'casualty_cnt', 'death_cnt', 'serious_injury_cnt', 'minor_injury_cnt', 'injury_report_cnt', 'repeat_cnt_21_25', 'lat', 'lon']}, {'file': '40_src_accident_list.csv', 'data_id': 'DAT-01', 'source_id': 'SRC38', 'name': 'TAAS 보행자 교통사고 목록', 'basis_column': 'occurred_year', 'basis_kind': 'year', 'columns': ['row_id', 'accident_no', 'occurred_year', 'occurred_month', 'day_night', 'gu', 'accident_severity', 'accident_type', 'violation', 'road_surface', 'weather', 'road_shape', 'offender_vehicle_type', 'victim_vehicle_type', 'victim_age_group', 'victim_injury_level', 'death_cnt', 'serious_injury_cnt', 'minor_injury_cnt', 'injury_report_cnt', 'ped_victim_yn'], 'key': 'row_id', 'numeric': ['death_cnt', 'serious_injury_cnt', 'minor_injury_cnt', 'injury_report_cnt']}, {'file': '47_src_zone_sign.csv', 'data_id': 'DAT-27', 'source_id': 'SRC24', 'name': '보호구역 표지판', 'basis_column': 'data_ref_date', 'basis_kind': 'date', 'columns': ['row_id', 'seq_no', 'old_zone_id_2022', 'target_facility_name_2022', 'linked_zone_id', 'link_method', 'gu_by_coord', 'admin_dong_name', 'lat', 'lon', 'grid_no', 'dist_to_zone_road_m', 'police_station', 'photo_file_name', 'data_ref_date', 'gid'], 'key': 'row_id', 'numeric': ['lat', 'lon', 'dist_to_zone_road_m']}, {'file': '48_src_ped_priority_candidate.csv', 'data_id': 'DAT-25', 'source_id': 'SRC33', 'name': '보행자 우선도로 후보지', 'basis_column': 'data_ref_date', 'basis_kind': 'date', 'columns': ['row_id', 'candidate_id', 'road_name', 'gu_by_coord', 'gu_raw', 'admin_dong_start', 'start_lat', 'start_lon', 'end_lat', 'end_lon', 'grid_no_start', 'length_m', 'straight_dist_m', 'length_note', 'road_min_width_m', 'one_way_yn', 'zone_road_within_10m', 'crossed_grid_cnt', 'photo_file_name', 'data_ref_date', 'gid'], 'key': 'row_id', 'numeric': ['start_lat', 'start_lon', 'end_lat', 'end_lon', 'length_m', 'straight_dist_m', 'road_min_width_m', 'crossed_grid_cnt']}]
MISSING = {"", r"\N", "NULL"}


def missing(value):
    return value is None or value.strip() in MISSING


def inspect_csv(raw, profile):
    reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    header = next(reader, [])
    if header != profile["columns"]:
        raise ValueError("header_mismatch")
    issues, dates, seen_keys, seen_rows = [], set(), set(), set()
    count = 0
    def issue(number, column, code):
        issues.append(dict(csv_record=number, column=column, code=code))
    for number, values in enumerate(reader, 2):
        count += 1
        if len(values) != len(header):
            issue(number, "*", "row_width_mismatch")
            continue
        signature = tuple(values)
        if signature in seen_rows:
            issue(number, "*", "duplicate_row")
        seen_rows.add(signature)
        row = dict(zip(header, values))
        key = row[profile["key"]]
        if missing(key):
            issue(number, profile["key"], "required_blank")
        elif key in seen_keys:
            issue(number, profile["key"], "duplicate_key")
        else:
            seen_keys.add(key)
        column = profile["basis_column"]
        value = row[column].strip()
        try:
            if missing(value):
                raise ValueError()
            if profile["basis_kind"] == "date":
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError()
                normalized = value
            elif profile["basis_kind"] == "short_year":
                # 이 자료의 21~25를 2021~2025로 해석합니다. 원문은 변경하지 않습니다.
                years = {str(y): str(2000+y) for y in range(21,26)}
                normalized = years[value]
            else:
                if not re.fullmatch(r"20[0-9]{2}", value):
                    raise ValueError()
                normalized = value
            dates.add(normalized)
        except (ValueError, KeyError):
            issue(number, column, "basis_missing_or_invalid")
        for column in profile["numeric"]:
            value = row[column].strip()
            if missing(value):
                continue  # Optional missing values remain missing; never converted to zero.
            try:
                if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value) or not Decimal(value).is_finite():
                    raise ValueError()
            except (ValueError, InvalidOperation):
                issue(number, column, "invalid_number")
    if count == 0:
        issue(1, "*", "empty_dataset")
    return dict(total_rows=count, issue_count=len(issues), affected_rows=len({i["csv_record"] for i in issues}),
                issues=issues, basis_values=sorted(dates),
                rule_scope="v2 CSV 칸 이름·첫 번째 ID 칸·기준일/연도·완전히 같은 행·선택 숫자 칸",
                team_rules_approved=False, a06_checked=False)


def process_file(path, profile, run_folder):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("input_file_missing_or_invalid")
    raw = path.read_bytes()
    inspection = inspect_csv(raw, profile)
    folder = run_folder / profile["data_id"]
    folder.mkdir(parents=True, exist_ok=False)
    archived = folder / "received.csv"
    archived.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    matches = hashlib.sha256(archived.read_bytes()).hexdigest() == digest
    unchanged = path.read_bytes() == raw
    basis = inspection["basis_values"]
    accepted = bool(basis) and matches and unchanged
    record = dict(
        data_id=profile["data_id"], source_id=profile["source_id"], name=profile["name"],
        input_name=path.name, source="팀 공유드라이브 v2_통합테이블_CSV_84개_261021.zip의 가공 CSV",
        original_status="가공본", original_collected_at=None,
        received_at=datetime.now(timezone(timedelta(hours=9))).isoformat(),
        operator="로컬 실행자 (팀 로그인 미연결)", operator_authenticated=False,
        run_id=run_folder.name, basis_column=profile["basis_column"], basis_values=basis,
        basis_precision="일" if profile["basis_kind"] == "date" else "연도",
        basis_rule="ref_year 21~25를 이 5개년 자료에 한해 2021~2025로 해석; 원문 변경 없음" if profile["basis_kind"] == "short_year" else "CSV의 기준일 또는 발생연도 값을 사용",
        receipt_status="접수 기록 생성" if accepted else "접수 보류",
        archive_status="실행별 복사 보관·내용 일치 확인" if matches else "보관 오류",
        sha256=digest, archived_file="received.csv", archive_matches_input=matches, source_unchanged=unchanged,
        validation=inspection, next_step_ready=accepted and not inspection["issues"],
        db_written=False, team_server_uploaded=False, approved_for_scoring=False,
        note="오류 원문 보존. 공통 서버의 회차·로그인·보관 권한·최종 검사 규칙은 별도 연결 필요.",
    )
    (folder/"receipt.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
    (folder/"validation.json").write_text(json.dumps(inspection,ensure_ascii=False,indent=2),encoding="utf-8")
    return record


def render(records, run_id):
    def t(v):
        return escape(str(v))
    rows=[]
    details=[]
    for r in records:
        v=r["validation"]; dates=r["basis_values"]
        period=(dates[0]+" ~ "+dates[-1]) if dates else "미확인"
        values=[r["data_id"],r["name"],v["total_rows"],period,r["original_status"],r["receipt_status"],r["archive_status"],v["issue_count"],"부분 검사 통과" if r["next_step_ready"] else "검토 필요"]
        rows.append("<tr>"+"".join("<td>"+t(x)+"</td>" for x in values)+"</tr>")
        errors="".join("<tr><td>"+t(i["csv_record"])+"</td><td>"+t(i["column"])+"</td><td>"+t(i["code"])+"</td></tr>" for i in v["issues"][:1000])
        details.append("<h2>"+t(r["data_id"])+" · "+t(r["name"])+"</h2><p>기준 칸: "+t(r["basis_column"])+" / 날짜 정밀도: "+t(r["basis_precision"])+" / "+t(r["basis_rule"])+"</p><p>오류가 있으면 CSV 레코드 번호·칸·이유를 표시합니다. 최대 1,000건을 화면에 표시하고 전체 오류는 각 자료의 validation.json에 보관합니다.</p><table><tr><th>CSV 레코드</th><th>칸</th><th>검사 코드</th></tr>"+errors+"</table>")
    heads=["DAT 번호","자료","행 수","실제 CSV의 날짜·연도 범위","원본 상태","A-03 접수","A-04 보관","A-05 검토 항목","부분 검사 결과"]
    total=sum(r["validation"]["total_rows"] for r in records)
    return """<!doctype html><html lang="ko"><meta charset="utf-8"><title>A-03~A-05 실제 가공 CSV 연결</title>
<style>body{font-family:'Malgun Gothic',sans-serif;margin:28px;color:#17263c;line-height:1.7}h1{font-size:26px}.notice{padding:16px;background:#fff3d6}.scroll{overflow:auto}table{border-collapse:collapse;font-size:14px}th,td{border:1px solid #ccd4df;padding:10px;vertical-align:top}th{background:#e9eff7;white-space:nowrap}h2{font-size:19px;margin-top:30px}</style>
<h1>A-03 → A-04 → A-05 실제 가공 CSV 연결</h1><div class="notice">팀 가공 CSV의 로컬 접수·실행별 복사 보관·부분 형식 검사 결과입니다. 제공기관 원본 확보, 실제 서버 업로드, DB 저장, 팀 로그인·회차·권한 연결, 산정 승인 결과가 아닙니다. 필수 칸·자료별 최종 규칙은 팀 검토 전이며, A-06 좌표 범위·공간 검사는 하지 않습니다. 빈 숫자 칸은 0으로 바꾸지 않습니다.</div><p>실행: """+t(run_id)+" · 파일 "+str(len(records))+"개 · "+str(total)+"행</p><div class=\"scroll\"><table><tr>"+"".join("<th>"+t(h)+"</th>" for h in heads)+"</tr>"+"".join(rows)+"</table></div>"+"".join(details)+"<p>원본 파일과 오류 행은 삭제·수정하지 않았습니다. 동일 자료의 재실행은 별도 실행 폴더에 보관합니다.</p></html>"


def run(root):
    input_folder=root/"inputs/a03_real"
    paths=[input_folder/p["file"] for p in PROFILES]
    # All files must exist before any receipt/archive output is made.
    if any(not p.is_file() or p.is_symlink() for p in paths):
        raise ValueError("8개 입력 파일을 먼저 준비해 주세요.")
    run_id="r_"+datetime.now(timezone(timedelta(hours=9))).strftime("%m%d_%H%M%S_")+uuid4().hex[:6]
    folder=root/"outputs/a03_flow"/run_id
    folder.mkdir(parents=True,exist_ok=False)
    records=[]
    for path,profile in zip(paths,PROFILES):
        r=process_file(path,profile,folder);records.append(r)
        print(r["data_id"],r["name"],r["validation"]["total_rows"],"행 / 검토 항목",r["validation"]["issue_count"],"건")
    (folder/"summary.json").write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding="utf-8")
    (folder/"flow_result.html").write_text(render(records,run_id),encoding="utf-8")
    print("실제 가공 CSV 8개 로컬 연결 확인 / DB 저장·팀 로그인·A-06 검사 없음")
    print("화면:",folder/"flow_result.html")
    return folder,records


if __name__=="__main__":
    try:
        run(Path(__file__).resolve().parent)
    except (OSError,ValueError,UnicodeError,csv.Error) as exc:
        raise SystemExit("연결 중단: "+str(exc))
