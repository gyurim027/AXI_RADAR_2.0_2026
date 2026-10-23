"""AI-05 법령 RAG ⑤ 기능 묶음 — 화면·백엔드가 부르는 세 가지
1) related_articles(problem_type, query): 후보의 문제 유형 → 관련 조문 (E-04, 사용자 화면 후보 상세)
   판정 유형 코드(T01 등)가 법령색인 'RADAR에서 쓴 곳'에 있으면 대응표 경로, 없으면 검색 경로
2) action_basis(ck_id): 조치 제안 표(대장 05_03) 한 줄 → 근거 조문 후보 (AI-10 문장 틀의 근거 조문 칸)
3) search(query): 질문형 검색 (어드민·개발 확인용)
"""
import json, re
from pathlib import Path
from .rag import LawIndex, arts_in, norm_law, NOT_FOUND

DATA = Path(__file__).resolve().parents[3] / 'data' / 'ai05'   # 저장소 루트/data/ai05

# 81 action_template(조치 제안 표, SQL v2 영문 컬럼) 칸 → 대장 05_03 칸 이름 (파일 action_table.json과 같은 꼴로 맞춤)
DB_COLS = {'item_id': '항목 ID', 'judgement_kind': '판정 결과 종류', 'check_item': '확인 항목', 'unknown_reason': '데이터로 모르는 이유',
           'to_check': '확인할 것 (MVP 포함)', 'action_kind': '조치 종류', 'action_sentence': '조치 제안 문장 (AI-10 초안 작성 후 채움)',
           'field_input_items': '현장 입력 항목 (확장 단계)', 'jurisdiction_id': '관할 ID', 'receiving_dept': '받는 부서 (05 관할 매핑의 1차 해결 부서)',
           'basis_status': '근거 상태', 'basis_article': '근거 조문', 'basis_article_source': '근거 조문 찾을 곳 (후보)', 'remark': '비고'}

def load_actions_from_db():
    """공용 DB의 81 action_template을 읽는다 (공통 연결 app/core/db.py, 읽기 전용 거래).
    .env에 RADAR_DB_*가 없거나 연결이 안 되면 None을 돌려주고, 파일(action_table.json)로 대신한다."""
    from app.core import db
    if not db.is_configured():
        return None, '파일 (RADAR_DB_HOST 없음)'
    try:
        sql = 'SELECT ' + ', '.join(f'`{c}`' for c in DB_COLS) + ' FROM action_template ORDER BY `item_id`'
        rows = [{DB_COLS[k]: v for k, v in r.items()} for r in db.read_only(sql)]
        return {r['항목 ID']: r for r in rows}, f'DB (action_template {len(rows)}행)'
    except Exception as e:                                   # DB가 꺼져 있어도 API는 켜지게 — 파일로 대신함
        return None, f'파일 (DB 연결 실패: {type(e).__name__})'

class LawService:
    REFS = re.compile(r'([가-힣ㆍ·\s]+?(?:법률|법|령|규칙|조례|지침))\s*(제\d+조(?:의\d+)?)')
    def __init__(self, data_dir=DATA):
        d = Path(data_dir)
        self.ix = LawIndex.load(d / 'law_index.pkl')
        self.criterion = json.load(open(d / 'criterion.json', encoding='utf-8'))
        self.actions, self.actions_source = load_actions_from_db()
        if self.actions is None:                               # DB가 없으면 대장 05_03을 옮긴 파일
            p = d / 'action_table.json'
            self.actions = {r['항목 ID']: r for r in json.load(open(p, encoding='utf-8'))} if p.exists() else {}

    def _refs_for_type(self, code):
        """판정 유형 코드(예: T18) → 법령색인에서 그 코드를 쓴 줄들의 (법령, 조항)"""
        pat = re.compile(rf'(?<![A-Za-z0-9]){re.escape(code)}(?![0-9])')
        refs = []
        for r in self.criterion:
            if r.get('종류') == '법령' and pat.search(str(r.get('RADAR에서 쓴 곳') or '')) and arts_in(r.get('조항·만든 곳')):
                refs.append((re.sub(r'\([^)]*\)', '', r['이름']).strip(), r['조항·만든 곳']))
        return refs

    def related_articles(self, problem_type=None, query=None, k=3, include_future=False):
        refs = self._refs_for_type(problem_type) if problem_type else []
        res = self.ix.answer(query=query, refs=refs or None, k=k, include_future=include_future)
        res['problem_type'] = problem_type
        return res

    def action_basis(self, ck_id, k=3):
        row = self.actions.get(ck_id)
        if not row: return {'ck_id': ck_id, 'result': '조치 제안 표에 없는 항목'}
        confirmed = str(row.get('근거 조문') or '')            # 81번 basis_article: 사람이 원문과 대조해 확정한 조문 (있으면 이걸 먼저)
        where = confirmed if self.REFS.search(confirmed) else str(row.get('근거 조문 찾을 곳 (후보)') or '')
        query = f"{row.get('확인 항목') or ''} {row.get('확인할 것 (MVP 포함)') or ''}".strip()
        refs = [(m.group(1).strip(), m.group(2)) for m in self.REFS.finditer(where)]
        if refs:                                                   # '도로교통법 제32조'처럼 조문까지 적혀 있으면 그대로 꺼냄
            res = self.ix.answer(refs=refs, k=k)
        else:                                                      # 법령 이름만 있으면 그 법령 안에서, 'AI-05로 찾음'이면 전체에서 검색
            laws = [n for n in self.ix.by_law if n in norm_law(where)] if 'AI-05' not in where else []
            laws = [n for n in laws if not any(n != m and n in m for m in laws)]   # '…증진법'과 '…증진법 시행규칙'이 둘 다 걸리면 긴 쪽만
            items = []
            for law_key in laws or [None]:
                law = next((c['law_name'] for c in self.ix.C if norm_law(c['law_name']) == law_key), None) if law_key else None
                # 법령을 이미 좁혔으니 포함률 기준을 낮춤(0.2). 법령을 모르면 기본 기준(0.4)
                items += self.ix.search(query, k=k, law=law, min_cover=0.2 if law else None)
            res = self.ix.answer(query=query, k=k) if not items else {'route': '검색(법령 지정)' if laws else '검색', 'result': '찾음',
                  'items': [{'cite': c['cite'], 'law_name': c['law_name'], 'article': c.get('article'), 'section': c.get('section'),
                             'status': c['status'], 'quote': c['text'], 'score': c.get('score'), 'cover': c.get('cover')} for c in items[:k]]}
        res.update(ck_id=ck_id, query=query, where=where, 근거_상태=row.get('근거 상태'), 확정_조문=bool(self.REFS.search(confirmed)))
        return res

    def search(self, query, k=5, include_future=False):
        return self.ix.answer(query=query, k=k, include_future=include_future)
