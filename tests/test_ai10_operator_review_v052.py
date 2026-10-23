"""실제 운영 DB나 data 파일을 변경하지 않는 6단계 단위 시험."""
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'app' / 'services' / 'ai10_operator_review.py'
spec = importlib.util.spec_from_file_location('ai10_operator_review', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def expect_error(fn, label):
    try:
        fn()
    except ValueError:
        print('통과 | ' + label)
        return
    raise AssertionError(label + ': 차단하지 못함')


def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        source = ROOT / 'data' / 'ai10_review_report_v3.json'
        store = td / 'review.json'
        count = mod.bootstrap(source, store)
        assert count == 14
        print('통과 | 초안 14건 로드')
        expect_error(lambda: mod.bootstrap(source, store), '실수로 재초기화 차단')
        expect_error(lambda: mod.decide('CK-03', '테스트담당', 'approve', '검토', False, store), '경고 미확인 승인 차단')
        mod.update_text('CK-03', '점자블록 상태를 현장 확인한 뒤 필요한 조치를 검토할 수 있습니다.', '테스트담당', store)
        state = mod.load_store(store)['items']['CK-03']
        assert state['revision'] == 1 and not state['approved']
        print('통과 | 수정 이력 및 미승인 유지')
        mod.decide('CK-03', '테스트담당', 'approve', '경고 확인 및 문장 검토', True, store, evidence_source='시험용 모의 근거(실제 원문 대조 아님)', evidence_checked=True)
        assert mod.load_store(store)['items']['CK-03']['approved']
        print('통과 | 명시적 승인과 이력 기록')
        expect_error(lambda: mod.update_text('CK-03', '무단 변경', '테스트담당', store), '승인 후 무단 변경 차단')
        mod.decide('CK-03', '테스트담당', 'revoke', '내용 재검토', store=store)
        assert not mod.load_store(store)['items']['CK-03']['approved']
        print('통과 | 승인 취소')
        mod.decide('CK-04', '테스트담당', 'reject', '검토 필요', store=store)
        assert mod.load_store(store)['items']['CK-04']['review_status'] == 'rejected'
        print('통과 | 반려')
        assert len(mod.load_store(store)['items']['CK-03']['events']) == 3
        assert json.loads(source.read_text(encoding='utf-8-sig'))['approved_count'] == 0
        print('통과 | 원본 보고서 변경 없음 · Gemini/DB 호출 없음')


if __name__ == '__main__':
    main()
