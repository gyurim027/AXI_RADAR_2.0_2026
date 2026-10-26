"""A-01 출처 목록 대조안. DB 수정·외부 접속 없음.
공통 프로젝트 루트에 이 파일을 놓고: uv run python run_a01_scope.py
입력: 앞서 저장한 outputs/a01_db/source_list.json
출력: outputs/a01_scope/catalog.html 및 catalog.json
"""
import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path

BASELINE = [{'data_id': 'DAT-01', 'name': '보행자 교통사고 목록', 'provider': '한국도로교통공단(TAAS)', 'reference': 'TAAS 교통사고분석시스템', 'document_basis': '2019-01~2025-12 (보행자 사고 4,726건) / 2023~2025 전체 사고 10,742건', 'cycle': '연간', 'source_id': 'SRC38', 'mapping_review_required': True, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-02', 'name': '보행자 교통사고 다발지역', 'provider': '한국도로교통공단(TAAS)', 'reference': 'TAAS 다발지분석', 'document_basis': '기준연도 2021~2025', 'cycle': '연간', 'source_id': 'SRC37', 'mapping_review_required': True, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-03', 'name': '전국교통사고다발지역표준데이터', 'provider': '한국도로교통공단', 'reference': '공공데이터포털 데이터 ID 15029185', 'document_basis': '사고연도 2012~2024 (기준일 2025-09-24)', 'cycle': '연간', 'source_id': 'SRC35', 'mapping_review_required': True, 'mapping_note': '출처에 같은 포털 번호가 있으나 6유형 통합 범위를 확인해야 합니다.'}, {'data_id': 'DAT-04', 'name': '수치지형도 인도(보도) 레이어', 'provider': '국토지리정보원', 'reference': '국토정보플랫폼 수치지형도 Ver2.0 1:5,000 (성남 35도엽)', 'document_basis': '2025년 제작', 'cycle': '미확인', 'source_id': 'SRC18', 'mapping_review_required': True, 'mapping_note': '수치지형도 전체 출처입니다. 보도 레이어와 원본 확보 여부는 별도 확인이 필요합니다.'}, {'data_id': 'DAT-05', 'name': '주정차 위반 단속 위치 현황', 'provider': '성남시', 'reference': '공공데이터포털 데이터 ID 15037104', 'document_basis': '2024-11-13~2025-12-31', 'cycle': '연간', 'source_id': 'SRC30', 'mapping_review_required': False, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-06', 'name': '보행자전용도로 표준데이터', 'provider': '성남시(3개 구청)', 'reference': '공공데이터포털 데이터 ID 15025443', 'document_basis': '2026-05-12', 'cycle': '반기', 'source_id': 'SRC16', 'mapping_review_required': False, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-07', 'name': '횡단보도 표준데이터', 'provider': '지방자치단체', 'reference': '공공데이터포털 데이터 ID 15028201', 'document_basis': '2026-05-29', 'cycle': '반기', 'source_id': 'SRC06', 'mapping_review_required': False, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-08', 'name': '어린이보호구역 표준데이터', 'provider': '지방자치단체', 'reference': '공공데이터포털 데이터 ID 15012891', 'document_basis': '2026-05-12', 'cycle': '반기', 'source_id': 'SRC03', 'mapping_review_required': False, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-09', 'name': '노인장애인보호구역 표준데이터', 'provider': '지방자치단체', 'reference': '공공데이터포털 데이터 ID 15034532', 'document_basis': '2026-05-12', 'cycle': '반기', 'source_id': 'SRC04', 'mapping_review_required': False, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-10', 'name': '전국 보호구역 현황 API (경찰청, 현행)', 'provider': '경찰청', 'reference': '공공데이터포털 데이터 ID 15142010', 'document_basis': '최종수정 2025~2026', 'cycle': '수시', 'source_id': 'SRC01', 'mapping_review_required': False, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-11', 'name': '행정동 연령별 주민등록 인구', 'provider': '행정안전부', 'reference': '공공데이터포털 데이터 ID 15097972', 'document_basis': '2026-08-31', 'cycle': '월간', 'source_id': 'SRC41', 'mapping_review_required': False, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-12', 'name': '보안등정보', 'provider': '성남시(3개 구청)', 'reference': '공공데이터포털 데이터 ID 15017320', 'document_basis': '2025-11-27', 'cycle': '연간', 'source_id': 'SRC07', 'mapping_review_required': False, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-13', 'name': '교통신호기 시설물현황', 'provider': '성남시', 'reference': '공공데이터포털 데이터 ID 15054833', 'document_basis': '2026-06-11', 'cycle': '연간', 'source_id': 'SRC09', 'mapping_review_required': False, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-14', 'name': '험프형 횡단보도 설치현황', 'provider': '성남시', 'reference': '공공데이터포털 데이터 ID 15042520', 'document_basis': '2026-06-11', 'cycle': '연간', 'source_id': 'SRC26', 'mapping_review_required': False, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-15', 'name': '옐로카펫 설치현황', 'provider': '성남시', 'reference': '공공데이터포털 데이터 ID 15042521', 'document_basis': '2026-06-11', 'cycle': '연간', 'source_id': 'SRC23', 'mapping_review_required': True, 'mapping_note': '파일과 2022년 조사 API가 함께 적혀 있어 사용할 버전을 확인해야 합니다.'}, {'data_id': 'DAT-16', 'name': '버스정류장 현황', 'provider': '성남시', 'reference': '공공데이터포털 15077307, 국토교통부 전국 버스정류장 위치정보(2025-10-31)', 'document_basis': '2026-04-08', 'cycle': '연간', 'source_id': 'SRC31', 'mapping_review_required': True, 'mapping_note': '정류장과 승하차가 한 출처에 함께 등록돼 있습니다. 파일을 따로 확인해야 합니다.'}, {'data_id': 'DAT-17', 'name': '정류소별 승하차 인원', 'provider': '경기데이터드림', 'reference': '경기데이터드림 정류소 승하차', 'document_basis': '2026-03-01~03-31 (일 단위)', 'cycle': '미확인', 'source_id': 'SRC31', 'mapping_review_required': True, 'mapping_note': '정류장과 승하차가 한 출처에 함께 등록돼 있습니다. 파일을 따로 확인해야 합니다.'}, {'data_id': 'DAT-18', 'name': '행정동 시간대별 유동인구', 'provider': '경기데이터드림(KT)', 'reference': '경기데이터드림', 'document_basis': '2026-02~03', 'cycle': '월간', 'source_id': 'SRC45', 'mapping_review_required': True, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-19', 'name': '도로종류별 교통량', 'provider': '한국건설기술연구원', 'reference': '도로종류별 교통량 및 좌표', 'document_basis': '2025', 'cycle': '연간', 'source_id': None, 'mapping_review_required': True, 'mapping_note': '현재 출처 목록에서 대응 항목을 정하지 못했습니다. 미수집 판정은 아닙니다.'}, {'data_id': 'DAT-20', 'name': '표준노드링크', 'provider': '국토교통부', 'reference': '국토교통부 ITS 표준노드링크', 'document_basis': '2026-09-14', 'cycle': '미확인', 'source_id': 'SRC19', 'mapping_review_required': True, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-21', 'name': '차로별 도로현황', 'provider': '성남시', 'reference': '공공데이터포털 데이터 ID 15000817', 'document_basis': '2026-06-03', 'cycle': '연간', 'source_id': 'SRC34', 'mapping_review_required': True, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-22', 'name': '지역안전지수', 'provider': '행정안전부', 'reference': '행정안전부 지역안전지수 산출 결과', 'document_basis': '2025년 발표(2024년 통계)', 'cycle': '연간', 'source_id': 'SRC51', 'mapping_review_required': True, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-23', 'name': '적치물 등 장애물', 'provider': '성남시', 'reference': '공공데이터포털 데이터 ID 15111670', 'document_basis': '2022-09~10', 'cycle': '1회성', 'source_id': 'SRC15', 'mapping_review_required': False, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-24', 'name': '우회전 사각지대', 'provider': '성남시', 'reference': '공공데이터포털 데이터 ID 15111666', 'document_basis': '2022-10~11', 'cycle': '1회성', 'source_id': 'SRC13', 'mapping_review_required': False, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-25', 'name': '보행자 우선도로 후보지', 'provider': '성남시', 'reference': '공공데이터포털 데이터 ID 15111668', 'document_basis': '2022-10', 'cycle': '1회성', 'source_id': 'SRC33', 'mapping_review_required': False, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-26', 'name': '도로 적색표면', 'provider': '성남시', 'reference': '공공데이터포털 데이터 ID 15111631', 'document_basis': '2022-07~09', 'cycle': '1회성', 'source_id': 'SRC22', 'mapping_review_required': False, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-27', 'name': '보호구역 표지판', 'provider': '성남시', 'reference': '공공데이터포털 데이터 ID 15111695', 'document_basis': '2022-07~09', 'cycle': '1회성', 'source_id': 'SRC24', 'mapping_review_required': False, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-28', 'name': '도로 조도·휘도', 'provider': '성남시', 'reference': '공공데이터포털 데이터 ID 15110579', 'document_basis': '2022-08~10', 'cycle': '1회성', 'source_id': 'SRC21', 'mapping_review_required': False, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-29', 'name': '교통약자 보호구역(성남시 CSV·API)', 'provider': '성남시', 'reference': '공공데이터포털 데이터 ID 15111694, 15111672', 'document_basis': '2022-07~09', 'cycle': '1회성', 'source_id': 'SRC02', 'mapping_review_required': False, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-30', 'name': '과속방지턱 현황', 'provider': '성남시', 'reference': '공공데이터포털 데이터 ID 15157263', 'document_basis': '2026-01-19', 'cycle': '미확인', 'source_id': 'SRC28', 'mapping_review_required': True, 'mapping_note': '자료명으로 대응 후보를 정했습니다. 포털 번호를 추가 확인해야 합니다.'}, {'data_id': 'DAT-31', 'name': '자전거도로 현황 (성남시, 전국자전거도로표준 성남분)', 'provider': '성남시', 'reference': '공공데이터포털 데이터 ID 15032469', 'document_basis': '2026-06-03', 'cycle': '미확인', 'source_id': 'SRC32', 'mapping_review_required': True, 'mapping_note': '자료명·제공처·출처 정보를 기준으로 연결한 검토안입니다. 팀의 최종 승인 결과는 아닙니다.'}, {'data_id': 'DAT-32', 'name': '안전신문고 신고', 'provider': '행정안전부', 'reference': '안전신문고 (경로 셋, ISS-023)', 'document_basis': '-', 'cycle': '수시', 'source_id': None, 'mapping_review_required': True, 'mapping_note': '민원 자료입니다. 공공데이터 출처 목록에 없다는 이유로 미수집으로 판정하지 않습니다.'}, {'data_id': 'DAT-33', 'name': '국민신문고 공개 민원 (민원 질의응답·답변 원문)', 'provider': '국민권익위원회', 'reference': '국민신문고 공개 화면 (쓰지 않음, ISS-012)', 'document_basis': '공개 동의 건, 처리완료 후 2년', 'cycle': '수시', 'source_id': None, 'mapping_review_required': True, 'mapping_note': '대장에는 쓰지 않는 경로로 기록돼 있습니다. 운영 범위는 팀 확인이 필요합니다.'}, {'data_id': 'DAT-34', 'name': '민원빅데이터 분석정보 API', 'provider': '국민권익위원회', 'reference': '공공데이터포털 데이터 ID 15128648', 'document_basis': '2024판', 'cycle': '제공 중지', 'source_id': None, 'mapping_review_required': True, 'mapping_note': '대장 작성 당시 제공 중지로 기록돼 있습니다. 현재 서비스 상태를 조회한 결과는 아닙니다.'}]

def make_catalog(sources):
    if not isinstance(sources, list):
        raise ValueError("출처 목록은 배열이어야 합니다.")
    indexed = {}
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("출처 기록 형식을 확인해 주세요.")
        key = source.get("source_id")
        if not isinstance(key, str) or key in indexed:
            raise ValueError("출처 번호 누락 또는 중복이 있습니다.")
        if "자료" not in source or "출처·번호" not in source:
            raise ValueError("출처 목록의 칸 이름이 다릅니다. 원본을 바꾸지 말고 확인해 주세요.")
        indexed[key] = source
    results = []
    for base in BASELINE:
        item = dict(base)
        source = indexed.get(base["source_id"])
        item.update(
            source_registered=source is not None,
            registered_name=source.get("자료") if source else None,
            registered_reference=source.get("출처·번호") if source else None,
            registered_file_note=source.get("남길 파일") if source else None,
            source_check_note=source.get("출처 확인 결과") if source else None,
            availability="미확인",
            original_status="미확인",
            original_collected_at=None,
            latest_status="판정 보류",
            status="대응 출처 등록" if source else "대응 출처 확인 필요",
        )
        results.append(item)
    used = {r["source_id"] for r in results if r["source_registered"]}
    return dict(
        baseline="기능정의 v0.5.3 A-01 DAT-01~34 / 기획·관리 대장 v0.4.2 데이터 목록",
        generated_at=datetime.now(timezone.utc).isoformat(),
        source_input="outputs/a01_db/source_list.json (저장된 DB 목록; 실시간 조회 아님)",
        source_count=len(sources), items=results,
        additional_sources=[{"source_id":s["source_id"],"name":s["자료"]} for s in sources if s["source_id"] not in used],
        db_written=False, all_files_verified=False, team_approved=False,
    )

def render(result):
    def cell(value):
        return escape("미확인" if value is None else str(value))
    rows = []
    for r in result["items"]:
        values = [r["data_id"],r["name"],r["source_id"],r["registered_name"],r["registered_reference"],r["status"],r["document_basis"],r["cycle"],r["availability"],r["original_status"],r["latest_status"],r["mapping_note"]]
        rows.append("<tr>"+"".join("<td>"+cell(v)+"</td>" for v in values)+"</tr>")
    headers=["DAT 번호","자료 이름","SRC 번호","DB 등록 자료명","DB 등록 출처","출처 대응 상태","대장에 기록된 기준일·기간","대장 갱신 주기","실제 파일 확보","원본 확인 상태","최신 여부","대응 근거·확인할 점"]
    extra="".join("<li>"+cell(s["source_id"])+" · "+cell(s["name"])+"</li>" for s in result["additional_sources"])
    return """<!doctype html><html lang="ko"><meta charset="utf-8"><title>A-01 자료 목록 대조안</title>
<style>body{font-family:'Malgun Gothic',sans-serif;margin:28px;line-height:1.7;color:#17263c}h1{font-size:26px}.notice{background:#fff4d9;padding:16px;border-left:5px solid #d19a20}.scroll{overflow:auto;max-height:70vh}table{border-collapse:collapse;font-size:14px}td,th{border:1px solid #ccd4df;padding:10px;min-width:120px;vertical-align:top}th{position:sticky;top:0;background:#e9eff7}td:nth-child(2),td:last-child{min-width:250px}</style>
<h1>A-01 자료 목록 대조안</h1>
<p>기능정의서 DAT-01~34와 저장된 실제 DB 출처 목록을 비교합니다. 팀 검토 전 자료입니다.</p>
<div class="notice">출처 등록은 파일 확보나 수집 성공을 뜻하지 않습니다. 이 프로그램은 실제 데이터 파일과 접수 기록을 대조하지 않으므로 파일 확보·원본 상태·최신 여부를 확정하지 않습니다. 대장의 기준일은 실제 파일에서 재확인한 날짜가 아닙니다. DAT-06의 별도 API 수집 결과도 여기서는 자동 반영하지 않습니다.</div>
<p>기준 목록: 34개 · DB 출처 기록: """+str(result["source_count"])+"""개. 두 목록은 번호와 묶음 기준이 달라 개수가 같을 필요가 없습니다.</p>
<div class="scroll"><table><thead><tr>"""+"".join("<th>"+cell(h)+"</th>" for h in headers)+"</tr></thead><tbody>"+"".join(rows)+"</tbody></table></div><h2>이 대조안의 34개 항목에 연결하지 않은 출처</h2><p>아래 항목은 삭제·제외 판정이 아닙니다. DAT-35 이후 자료 등 별도 범위일 수 있습니다.</p><ul>"+extra+"</ul><p>다음 확인: 자료별 실제 파일·수집 기록, 기준일, 원본 상태, 갱신 기준을 검증하고 팀과 대응표를 확정합니다. DB 수정·자동 수집·최신 판정은 실행하지 않았습니다.</p></html>"

def main():
    root=Path(__file__).resolve().parent
    source_path=root/"outputs/a01_db/source_list.json"
    if not source_path.is_file():
        raise SystemExit("outputs/a01_db/source_list.json이 없습니다. 프로젝트 루트에 이 프로그램을 넣어 주세요.")
    try:
        result=make_catalog(json.loads(source_path.read_text(encoding="utf-8-sig")))
    except (ValueError, TypeError) as exc:
        raise SystemExit("목록 생성 중단: "+str(exc))
    folder=root/"outputs/a01_scope"
    folder.mkdir(parents=True,exist_ok=True)
    (folder/"catalog.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    (folder/"catalog.html").write_text(render(result),encoding="utf-8")
    print("기준 자료:",len(result["items"]),"개 / DB 출처:",result["source_count"],"개")
    print("출처 대응 검토안을 만들었습니다. 파일 확보·최신 여부를 확정한 결과는 아닙니다.")
    print("화면:",folder/"catalog.html")

if __name__=="__main__":
    main()
