"""AI-05 법령 RAG ④ 평가 — 법령색인(57 criterion)을 정답으로 씀
A. 대응표 경로: 색인의 (법령, 조항)이 원문에서 실제로 꺼내지는가
B. 검색 경로: 색인의 '확인한 내용'을 질문으로 넣었을 때 정답 법령·조가 1등 / 5등 안에 드는가
C. 못 찾음: 법령과 관계없는 질문에 '보유 원문에서 못 찾음'이 나오는가
실행: python -m app.services.ai05.evaluate data/ai05/law_index.pkl data/ai05/criterion.json data/ai05/eval_report.json
"""
import json, re, sys
from .rag import LawIndex, norm_law, arts_in, NOT_FOUND

NEGATIVE = ['오늘 점심 메뉴 추천', '프로야구 순위', '아이폰 배터리 교체 비용', '여름휴가 여행지', '주식 배당금 세금',
            '김치찌개 끓이는 법', '노트북 추천', '영화 개봉 일정', '강아지 산책 시간', '커피 원두 고르는 법']

def law_hit(item, law, arts):
    if norm_law(item['law_name']) != norm_law(law): return False
    return (not arts) or item.get('article') in arts

def main(index_path, criterion_json, out):
    rep = run(LawIndex.load(index_path), json.load(open(criterion_json, encoding='utf-8')))
    json.dump(rep, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(brief(rep), ensure_ascii=False))
    return rep

def brief(rep):
    return {k: v for k, v in rep.items() if not k.endswith('상세')}

def run(ix, rows):
    """색인(ix) 하나를 법령색인 rows로 평가 (임베딩을 붙인 색인도 그대로 넣을 수 있음)"""
    have = set(ix.by_law)
    A, B = [], []
    for r in rows:
        law = re.sub(r'\([^)]*\)', '', r['이름'] or '').strip()
        if r.get('종류') != '법령' or norm_law(law) not in have: continue      # 보유하지 않은 법령·공식문서는 뺌
        arts = arts_in(r.get('조항·만든 곳'))
        if arts:
            got = {it['article'] for it in ix.answer(refs=[(law, r['조항·만든 곳'])])['items']}
            A.append({'id': r['criterion_id'], 'law': law, 'arts': arts, 'found': sorted(got & set(arts)), 'ok': set(arts) <= got})
        q = (r.get('확인한 내용(판·시행일)') or '')[:80]
        if len(q) < 10 or q.startswith('원본 파일'): continue
        res = ix.search(q, k=5)
        B.append({'id': r['criterion_id'], 'q': q, 'law': law, 'arts': arts,
                  'top1': bool(res) and law_hit(res[0], law, arts), 'top5': any(law_hit(x, law, arts) for x in res),
                  'law_top5': any(norm_law(x['law_name']) == norm_law(law) for x in res),
                  'got': [x['cite'] for x in res[:3]]})
    C = [{'q': q, 'not_found': ix.answer(query=q)['result'] == NOT_FOUND} for q in NEGATIVE]
    rate = lambda xs, k: round(sum(x[k] for x in xs) / max(len(xs), 1), 3)
    rep = {'A_대응표': {'건수': len(A), '전부 꺼냄': rate(A, 'ok')}, 'B_검색': {'건수': len(B), '1등 정답': rate(B, 'top1'), '5등 안 정답': rate(B, 'top5'), '5등 안 법령만 맞음': rate(B, 'law_top5')},
           'C_못찾음': {'건수': len(C), '못 찾음으로 나옴': rate(C, 'not_found')}, 'A_상세': A, 'B_상세': B, 'C_상세': C}
    return rep

if __name__ == '__main__':
    main(*sys.argv[1:4])
