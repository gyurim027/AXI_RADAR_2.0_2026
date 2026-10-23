"""AI-10 16개 비식별 민원 fixture의 CK 연결 '시험 설정' 무결성 검사.

주의: 민원 분류기나 실제 후보 매핑 구현이 아니다. Gemini/API/DB 호출 없음.
실행: uv run python tests/test_ai10_complaint_fixtures.py
"""
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
SAMPLES = DATA / 'RADAR_AI10_민원샘플_정리_v1.json'
RULES = DATA / 'ai10_ck_rules_v0.4.json'
REPORT = DATA / 'ai10_complaint_fixture_report_v1.json'
REQUIRED = ('sample_id', 'source_row_number', 'registered_date', 'sanitized_title',
            'complaint_claim_summary', 'ai10_test_scope', 'ck_candidate',
            'ck_mapping_status', 'real_ai10_input_allowed')
EXPECTED_COUNTS = {'적합': 3, '조건부': 5, '비대상': 8}


def main():
    samples = json.loads(SAMPLES.read_text(encoding='utf-8-sig'))
    rules = json.loads(RULES.read_text(encoding='utf-8-sig'))
    records = samples['records']
    rule_ids = {r['rule_id'] for r in rules['rules']}
    counts = Counter(r.get('ai10_test_scope') for r in records)
    seen = set()
    results = []
    for r in records:
        issues = []
        for k in REQUIRED:
            if k not in r:
                issues.append(f'필수 필드 없음: {k}')
        sid = r.get('sample_id')
        if sid in seen:
            issues.append('샘플 ID 중복')
        seen.add(sid)
        scope = r.get('ai10_test_scope')
        ck = r.get('ck_candidate')
        if scope not in EXPECTED_COUNTS:
            issues.append('범위 값 오류')
        if ck is not None and ck not in rule_ids:
            issues.append('기준표에 없는 CK 번호')
        if scope == '적합' and ck is None:
            issues.append('적합 사례에 CK 잠정 후보 없음')
        if scope != '적합' and ck is not None:
            issues.append('조건부/비대상에 확정처럼 CK 후보 연결됨')
        if r.get('real_ai10_input_allowed') is not False:
            issues.append('실제 운영 입력 허용 상태: 차단 필요')
        if scope == '적합' and '잠정' not in str(r.get('ck_mapping_status', '')):
            issues.append('CK 연결이 잠정임을 명시하지 않음')
        results.append({
            'sample_id': sid, 'source_row_number': r.get('source_row_number'),
            'scope': scope, 'ck_candidate': ck,
            'fixture_valid': not issues, 'issues': issues,
            'meaning_verified': False, 'operation_mapping_approved': False,
        })
    global_issues = []
    if len(records) != samples.get('record_count'):
        global_issues.append('기록 수 메타데이터 불일치')
    if dict(counts) != EXPECTED_COUNTS:
        global_issues.append('사례별 활용 분류 개수 예상값 불일치')
    if dict(counts) != samples.get('scope_counts'):
        global_issues.append('활용 분류 개수 메타데이터 불일치')
    report = {
        'purpose': 'AI-10 개발용 민원 샘플 무결성 검사; 운영 분류·CK 적용 승인 아님',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'total': len(records), 'scope_counts': dict(counts),
        'valid_fixture_count': sum(item['fixture_valid'] for item in results),
        'meaning_verified_count': 0, 'approved_mapping_count': 0,
        'global_issues': global_issues, 'results': results,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"민원 샘플: {len(records)}건 | 적합 {counts['적합']} / 조건부 {counts['조건부']} / 비대상 {counts['비대상']}")
    print(f"형식·연결 후보 무결성 통과: {report['valid_fixture_count']}/{len(records)}건")
    print('내용 의미 검증 및 운영 CK 매핑 승인: 0건 (수행하지 않음)')
    print('Gemini 호출·운영 DB 적재: 없음')
    for it in results:
        if it['issues']:
            print(f"확인 필요: {it['sample_id']}: {', '.join(it['issues'])}")
    for issue in global_issues:
        print(f'전체 확인 필요: {issue}')
    print(f'보고서: {REPORT}')
    if report['valid_fixture_count'] != len(records) or global_issues:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
