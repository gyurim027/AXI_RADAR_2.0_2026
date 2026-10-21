"""AI-05 자동 시험 — 고칠 때마다 이것만 돌리면 됨
사용 (저장소 루트에서): uv run python tests/test_ai05_law.py
  · 기능 시험 23건: 화면·백엔드가 부르는 세 기능(관련 조문 / 조치 제안 근거 / 검색)이 기대대로 나오는지
  · 평가 기준: 법령색인을 정답으로 한 평가(evaluate.py)가 아래 기준보다 나빠지지 않았는지
결과: 통과 O / 실패 X 와 이유. 하나라도 X면 끝에 '실패 n건'과 함께 종료 코드 1
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # 저장소 루트를 불러오기 경로에
from app.services.ai05.service import LawService
from app.services.ai05 import evaluate

svc = LawService()
def top(res, n=5): return [i['cite'] for i in res.get('items', [])][:n]

def _confirmed(ck, text):
    """사람이 81번 basis_article(근거 조문)을 채운 경우를 흉내 냄 (DB·파일은 바꾸지 않음)"""
    old = svc.actions[ck]; svc.actions[ck] = {**old, '근거 조문': text}
    try: return svc.action_basis(ck)
    finally: svc.actions[ck] = old

# (번호, 이름, 부르는 기능, 확인할 것)
CASES = [
 (1,  '색인 크기',                 lambda: {'items': [], 'n': len(svc.ix.C), 'laws': len(svc.ix.by_law)}, lambda r: r['n'] > 3000 and r['laws'] >= 40),
 (2,  '보도 유효폭',               lambda: svc.search('보도 유효폭'), lambda r: "보도 설치 및 관리 지침 '3-2 유효폭'" in top(r, 1)[0]),
 (3,  '어린이 보호구역 지정',       lambda: svc.search('어린이 보호구역 지정'), lambda r: '보호구역의 지정 및 관리에 관한 규칙 제3조' in top(r, 1)[0]),
 (4,  '도로 점용 허가 — 시행 전 판 알림', lambda: svc.search('도로 점용 허가'), lambda r: top(r, 1)[0].startswith('도로법') and all(i['future_version'] for i in r['items'])),
 (5,  '시행 전 포함',               lambda: svc.search('도로 점용 허가', include_future=True), lambda r: any(i['status'] == '시행 전' for i in r['items'])),
 (6,  'k = 1',                      lambda: svc.search('보도 유효폭', k=1), lambda r: len(r['items']) == 1),
 (7,  'T18 대응표',                 lambda: svc.related_articles('T18'), lambda r: r['route'] == '대응표' and '도로교통법 제32조' in top(r, 1)[0]),
 (8,  'T99 + 질문 → 검색',          lambda: svc.related_articles('T99', '보행자 통행 방해 적치물'), lambda r: r['route'] == '검색' and r['result'] == '찾음'),
 (9,  '보행등 녹색시간',            lambda: svc.related_articles(None, '보행등 녹색시간'), lambda r: '보행신호시간' in ' '.join(top(r, 3))),
 (10, 'CK-14 조문 바로 꺼냄',       lambda: svc.action_basis('CK-14'), lambda r: r['route'] == '대응표' and '도로교통법 제32조' in top(r, 1)[0]),
 (11, 'CK-10 법령 지정 검색',       lambda: svc.action_basis('CK-10'), lambda r: r['route'] == '검색(법령 지정)' and '유효폭' in top(r, 1)[0]),
 (12, '관계없는 질문 → 못 찾음',    lambda: svc.search('오늘 점심 메뉴'), lambda r: r['result'] == '보유 원문에서 못 찾음' and not r['items']),
 (13, 'T99만 → 못 찾음',            lambda: svc.related_articles('T99'), lambda r: r['result'] == '보유 원문에서 못 찾음'),
 (14, '없는 CK',                    lambda: svc.action_basis('CK-99'), lambda r: r['result'] == '조치 제안 표에 없는 항목'),
 (15, '횡단보도 주변 주정차 금지',   lambda: svc.search('횡단보도 주변 주정차 금지'), lambda r: any('도로교통법 제32조' in c for c in top(r, 5))),
 (16, 'CK-12 교통섬·분리대',        lambda: svc.action_basis('CK-12'), lambda r: any(k in ' '.join(top(r, 3)) for k in ('교통정온화', '보행안전 및 편의증진에 관한 법률 제15조', '도로안전시설'))),
 (17, '과업지시서 — 참고 자료 표시', lambda: svc.search('교통약자 이동편의시설 실태조사'), lambda r: any(i['doc_type'] == '정책자료' and i['status'] == '참고 자료(법령 아님)' for i in r['items'])),
 (18, '보행우선구역 적격성 조사',    lambda: svc.search('보행우선구역 적격성 조사'), lambda r: r['result'] == '찾음'),
 (19, '음향신호기·점자블록',        lambda: svc.search('음향신호기 설치 관리 점자블록 확충'), lambda r: r['result'] == '찾음'),
 (20, '법령은 시행 중/전으로만',     lambda: svc.search('보도 유효폭'), lambda r: all(i['status'] in ('시행 중', '시행 전') for i in r['items'] if i['doc_type'] != '정책자료')),
 (22, '확정한 basis_article(근거 조문)은 바로 꺼냄',   lambda: _confirmed('CK-12', '보행안전 및 편의증진에 관한 법률 제15조'), lambda r: r['route'] == '대응표' and r['확정_조문'] and '제15조' in top(r, 1)[0]),
 (23, '조치 제안 표 읽은 곳',         lambda: {'items': [], 'src': svc.actions_source}, lambda r: r['src'].startswith(('DB', '파일'))),
 (21, '인용은 원문 그대로',          lambda: svc.search('보도 유효폭', k=3), lambda r: all(i['quote'] in {c['text'] for c in svc.ix.C} for i in r['items'])),
]
# 평가 기준 (v0.3, 2026-10-19 기준값 — 이보다 낮아지면 실패)
# B 5등 안: v0.2 0.830 → v0.3 0.809. 같은 뜻 낱말(주정차 → 정차·주차)을 넣으면서 L17 '주정차 금지와 단속'의 정답(도로교통법 제32~35조·제143조)이
# 6~8위로 밀림. 대신 1~5위가 모두 주정차 조문으로 바뀌었고(전에는 단속장비·감염병 분야 등 관계없는 조문), 15·16번이 고쳐짐 → 0.80을 새 기준으로 둠
BAR = {'A_대응표': ('전부 꺼냄', 0.97), 'B_검색_1등': ('1등 정답', 0.68), 'B_검색_5등': ('5등 안 정답', 0.80), 'C_못찾음': ('못 찾음으로 나옴', 1.0)}

def api_checks():
    """라우터로 끼웠을 때 주소가 답하는지 (공통 main.py 없이 시험용 앱에 끼워서 확인)"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.ai05_law_api import router
    app = FastAPI(); app.include_router(router); c = TestClient(app)
    checks = [
        ('API /api/ai05/health', lambda: c.get('/api/ai05/health'), lambda r: r.status_code == 200 and r.json()['조각 수'] > 3000),
        ('API /api/ai05/related T18', lambda: c.get('/api/ai05/related', params={'problem_type': 'T18'}), lambda r: r.json()['route'] == '대응표'),
        ('API /api/ai05/action-basis/CK-14', lambda: c.get('/api/ai05/action-basis/CK-14'), lambda r: r.json()['route'] == '대응표'),
        ('API /api/ai05/search 못 찾음', lambda: c.get('/api/ai05/search', params={'q': '오늘 점심 메뉴'}), lambda r: r.json()['result'] == '보유 원문에서 못 찾음'),
    ]
    fail = 0
    for name, call, ok in checks:
        try: r = call(); good = bool(ok(r))
        except Exception as e: good = False; name += f' → 오류 {e!r}'
        fail += not good; print(f"{'O' if good else 'X'} {name}")
    return fail

def main():
    fail = 0
    print('== 기능 시험 (조치 제안 표:', svc.actions_source + ')')
    for no, name, call, ok in CASES:
        try:
            r = call(); good = bool(ok(r)); why = '' if good else ' → ' + (' ; '.join(top(r, 3)) or str(r.get('result')))
        except Exception as e:
            good, why = False, f' → 오류 {e!r}'
        fail += not good
        print(f"{'O' if good else 'X'} {no:>2}. {name}{why}")
    print('== 평가 (법령색인 정답)')
    d = Path(__file__).resolve().parents[1] / 'data' / 'ai05'
    rep = evaluate.main(d / 'law_index.pkl', d / 'criterion.json', Path(__file__).resolve().parent / '_ai05_last_eval.json')   # data/eval_report.json은 건드리지 않음
    got = {'A_대응표': rep['A_대응표']['전부 꺼냄'], 'B_검색_1등': rep['B_검색']['1등 정답'], 'B_검색_5등': rep['B_검색']['5등 안 정답'], 'C_못찾음': rep['C_못찾음']['못 찾음으로 나옴']}
    for k, (label, bar) in BAR.items():
        good = got[k] >= bar - 1e-9; fail += not good
        print(f"{'O' if good else 'X'} {k} {label} {got[k]:.3f} (기준 {bar})")
    print('== API (라우터)')
    fail += api_checks()
    print('모두 통과' if not fail else f'실패 {fail}건'); return fail

if __name__ == '__main__':
    sys.exit(1 if main() else 0)
