"""AI-10 CK-01~14 일괄 초안 생성 시험 (운영자 승인/DB 저장 없음).
실행: uv run python tests/test_ai10_all_rules.py
한 건 사전 시험: uv run python tests/test_ai10_all_rules.py --limit 1
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.ai10_draft import RULES_PATH, generate_draft


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=14, help='호출할 CK 개수 (기본 14)')
    parser.add_argument('--pause', type=float, default=8, help='호출 사이 대기 초 (기본 8)')
    args = parser.parse_args()
    if not 1 <= args.limit <= 14 or args.pause < 0:
        parser.error('--limit은 1~14, --pause는 0 이상이어야 합니다.')

    data = json.loads(RULES_PATH.read_text(encoding='utf-8'))
    rules = data['rules']
    ids = [r['rule_id'] for r in rules]
    if len(ids) != 14 or len(set(ids)) != 14 or set(ids) != {f'CK-{i:02d}' for i in range(1, 15)}:
        raise RuntimeError('CK 기준표의 ID·개수가 CK-01~14와 일치하지 않습니다.')

    results = []
    stopped_reason = None
    for index, rule in enumerate(rules[:args.limit], start=1):
        rule_id = rule['rule_id']
        print(f'[{index}/{args.limit}] {rule_id} 생성 시작...', flush=True)
        started = time.perf_counter()
        try:
            response = generate_draft(rule_id)
            elapsed = round(time.perf_counter() - started, 2)
            record = {
                'rule_id': rule_id,
                'status': 'draft_needs_human_review',
                'elapsed_seconds': elapsed,
                'draft_template': response.draft_template,
                'review_note': response.review_note,
                'manual_check': {
                    '기준표_밖_조치': '검토 필요',
                    '없는_법령_기관_수치': '검토 필요',
                    '판단상태_왜곡': '검토 필요',
                    '문장_표현': '검토 필요',
                },
            }
            print(f'  성공: {elapsed:.2f}초 (내용 정확성은 아직 미판정)', flush=True)
        except Exception as exc:
            elapsed = round(time.perf_counter() - started, 2)
            detail = str(exc)
            # 오류 출력에 API 키 또는 전체 요청을 넣지 않도록 메시지 길이를 제한
            print(f'  실패: {type(exc).__name__}', flush=True)
            record = {'rule_id': rule_id, 'status': 'error', 'elapsed_seconds': elapsed,
                      'error_type': type(exc).__name__}
            # 무료 할당량/모델 접근 문제 시 반복 호출하지 않음
            if any(token in detail.lower() for token in ['429', 'resource_exhausted', 'quota', 'billing', '403', 'permission_denied']):
                stopped_reason = f'{rule_id}: 사용 한도 또는 권한 관련 오류로 중단 ({type(exc).__name__})'
        results.append(record)
        if stopped_reason:
            print(stopped_reason, flush=True)
            break
        if index < args.limit and args.pause:
            time.sleep(args.pause)

    report = {
        'purpose': 'AI-10 CK 생성 시험용; 운영자 미승인; 서비스·DB 적재 금지',
        'source': data.get('source'),
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'requested': args.limit,
        'completed_calls': len(results),
        'success': sum(r['status'] == 'draft_needs_human_review' for r in results),
        'errors': sum(r['status'] == 'error' for r in results),
        'stopped_reason': stopped_reason,
        'results': results,
    }
    output = ROOT / 'data' / 'ai10_draft_test_results.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'결과 파일: {output}\n성공 {report["success"]}건 / 실패 {report["errors"]}건')
    print('주의: 성공은 API·JSON 생성 성공만 뜻하며, 내용 검증/운영자 승인이 아닙니다.')


if __name__ == '__main__':
    main()
