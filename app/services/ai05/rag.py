"""AI-05 법령 RAG ③ 색인·찾기
- 대응표 경로: 조문을 알면(예: '도로교통법 제32조', 판정 유형 'T18') 원문에서 그 조를 그대로 꺼냄
- 검색 경로: 대응표에 없으면 BM25(형태소 낱말) 검색. 임베딩(공통 LLM 모듈 call_embed, embed.py)이 붙어 있으면 함께 써서 순위를 섞음(RRF)
지킬 것(기능정의서 05 AI-05): 원문 조각만 그대로 인용 · 없는 조문 번호를 만들지 않음 · 못 찾으면 '보유 원문에서 못 찾음' ·
시행 전 판은 '시행 전'으로 따로 표시 · 법 해석·위반 판단을 하지 않음
"""
import json, math, os, pickle, re
from pathlib import Path
from kiwipiepy import Kiwi
from rank_bm25 import BM25Okapi

KEEP = ('NN', 'VV', 'VA', 'XR', 'SL', 'SN', 'SH')          # 명사·동사·형용사 어간·어근·외국어·숫자·한자
ABBR = {'보행안전법': '보행안전 및 편의증진에 관한 법률', '교통약자법': '교통약자의 이동편의 증진법', '공공데이터법': '공공데이터의 제공 및 이용 활성화에 관한 법률',
        '정보공개법': '공공기관의 정보공개에 관한 법률', '재난안전법': '재난 및 안전관리 기본법', '보호구역 규칙': '어린이ㆍ노인 및 장애인 보호구역의 지정 및 관리에 관한 규칙'}
NOT_FOUND = '보유 원문에서 못 찾음'
# 같은 뜻 낱말 묶음 (질문에만 더함). 질문 낱말이 원문에서 다른 꼴로 쓰이는 경우만 넣음 — 넣을 때마다 tests/run_tests.py로 확인
# 예: 질문 "주정차" ↔ 도로교통법 제32조 "정차·주차" / 질문 "인도" ↔ 원문 "보도" / "보행섬" ↔ "교통섬"
SYN = {'주정차': ['정차', '주차'], '불법주차': ['주차'], '인도': ['보도'], '보행섬': ['교통섬'], '교통섬': ['보행섬'],
       '노점': ['노점상', '적치물'], '턱낮춤': ['턱낮추기', '연석'], '점자블럭': ['점자블록'], '보행신호': ['보행자신호', '녹색신호'],
       '대피': ['교통섬', '안전지대']}   # 횡단보도 '중간 대피 공간' ↔ 원문 '교통섬'·'안전지대' (CK-12)
_kiwi = None

def tokens(text):
    global _kiwi
    _kiwi = _kiwi or Kiwi()
    return [t.form for t in _kiwi.tokenize(text) if t.tag.startswith(KEEP) and len(t.form) > 1 or t.tag == 'SN']

def norm_law(name):
    """'보행안전법 시행령' / '도로교통법 (법률 제21246호)' → 원문 법령 이름(괄호·공백·가운뎃점 차이 무시)으로 비교할 키"""
    name = re.sub(r'\([^)]*\)', '', name or '').strip()
    for a, full in ABBR.items():
        if name == a or name.startswith(a + ' '): name = full + name[len(a):]; break
    return re.sub(r'[\s·ㆍ・]', '', name)

def arts_in(s):
    """'제32조~제35조, 제143조' / '제12조 제1항, 제12조의2' → ['제32조','제33조','제34조','제35조','제143조','제12조','제12조의2']"""
    out = []
    for a, b in re.findall(r'제(\d+)조\s*~\s*제(\d+)조', s or ''):
        out += [f'제{n}조' for n in range(int(a), int(b) + 1)]
    out += re.findall(r'제\d+조(?:의\d+)?(?!\s*~)', s or '')
    return list(dict.fromkeys(out))

class LawIndex:
    def __init__(self, chunks):
        self.C = chunks
        toks = [tokens(f"{c['law_name']} {c.get('article_title') or c.get('section') or ''} {c['text']}") for c in chunks]
        self.tokset = [set(t) for t in toks]                      # '못 찾음' 판단용: 질문 단어가 조각에 얼마나 들어 있나
        self.bm = BM25Okapi(toks)
        self._max_idf = max(self.bm.idf.values()) * 1.2
        self.emb = None                                           # attach_embeddings()로 켬 (embed.py)
        self.by_law = {}
        for i, c in enumerate(chunks): self.by_law.setdefault(norm_law(c['law_name']), []).append(i)

    # ---------- 저장·불러오기 ----------
    @classmethod
    def build(cls, chunks_jsonl):
        return cls([json.loads(l) for l in open(chunks_jsonl, encoding='utf-8')])
    def save(self, path):
        pickle.dump(self, open(path, 'wb'))
    @staticmethod
    def load(path):
        return pickle.load(open(path, 'rb'))

    # ---------- 임베딩(선택, embed.py) ----------
    def attach_embeddings(self, vectors, embed_query, sim_min=None):
        """조각별 숫자 묶음(길이 1)과 질문을 숫자로 바꾸는 함수를 붙인다. 모델은 공통 LLM 모듈(call_embed)이 부른다.
        sim_min: 이보다 덜 비슷하면 임베딩만으로는 '찾음'으로 치지 않음 (관계없는 질문으로 정한 값)"""
        self.emb, self._embed_query, self.sim_min = vectors, embed_query, sim_min

    def _query_sim(self, query):
        """질문과 모든 조각의 유사도. 임베딩이 없거나 호출이 실패하면 None (낱말 검색만)"""
        if getattr(self, 'emb', None) is None: return None
        try:
            return self.emb @ self._embed_query(query)
        except Exception:                                         # 공용 PC Ollama가 꺼져 있는 등 → 이번 질문은 낱말 검색만
            return None

    # ---------- 대응표 경로: 조문 바로 꺼내기 ----------
    def article(self, law, article_no, include_future=False):
        """law='도로교통법', article_no='제32조' → 그 조의 조각들(항까지). 시행 중 판을 먼저"""
        idx = self.by_law.get(norm_law(law), [])
        hits = [self.C[i] for i in idx if self.C[i].get('article') == article_no and not self.C[i].get('addenda')]
        now = [c for c in hits if c['status'] == '시행 중']
        return hits if include_future else (now or hits)

    REF = re.compile(r'(?P<law>[가-힣ㆍ·\s]+?(?:법률|법|령|규칙|조례|지침))\s*(?:시행령|시행규칙)?\s*(?P<art>제\d+조(?:의\d+)?)')
    def parse_refs(self, s):
        """'도로교통법 제32조~제35조, 제143조' 같은 글에서 (법령, 조) 목록. 법령 이름이 없으면 앞의 이름을 이어 씀"""
        out, law = [], None
        for part in re.split(r'[,，/·]|및', s):
            m = self.REF.search(part)
            if m: law = m['law'].strip(); out.append((law, m['art']))
            else:
                for a in re.findall(r'제\d+조(?:의\d+)?', part):
                    if law: out.append((law, a))
        rng = re.search(r'(제(\d+)조)\s*~\s*제(\d+)조', s)          # 제32조~제35조 → 32,33,34,35
        if rng and law:
            out += [(law, f'제{n}조') for n in range(int(rng[2]), int(rng[3]) + 1)]
        return list(dict.fromkeys(out))

    # ---------- 검색 경로 ----------
    SYN_W = 0.5          # 같은 뜻 낱말 무게 (tests/run_tests.py로 정함)
    TITLE_W = 0          # 조문 제목 일치 가산 — 시험해 보니 다른 결과를 깨서 끔 (2026-10-19)
    ONE_PER_CITE = True  # 같은 인용은 결과에 한 번만
    def _titles(self):
        if getattr(self, '_tt', None) is None:
            self._tt = [set(tokens(c.get('article_title') or c.get('section') or '')) for c in self.C]
        return self._tt
    EMB_W = 1.0          # 임베딩 순위 무게 (낱말 순위 = 1). 비교 결과가 낮으면 조정 (docs/ai05/embedding.md)
    POOL = 200           # 낱말·임베딩 각각 위에서 몇 개까지 섞을지
    MIN_COVER = 0.4      # 희귀도 가중 포함률 기준. 2026-10-18 평가: 0.4에서 5등 안 정답 83% · 관계없는 질문 10/10 걸러냄 (evaluate.py)

    def search(self, query, k=5, include_future=False, law=None, min_score=None, min_cover=None):
        q = tokens(query)
        if not q: return []
        qs = set(q); cover_need = self.MIN_COVER if min_cover is None else min_cover
        alt = {x: [y for w in SYN.get(x, []) for y in tokens(w)] for x in qs}           # 질문 낱말별 같은 뜻 낱말
        s = self.bm.get_scores(q)
        extra = [y for x in q for y in alt[x] if y not in qs]
        if extra and self.SYN_W:                                  # 같은 뜻 낱말은 덜 무겁게 더함
            s = s + self.SYN_W * self.bm.get_scores(extra)
        if self.TITLE_W:                                          # 질문 낱말이 조문 제목·소제목에 있으면 조금 더
            tt = self._titles()
            want = qs | set(extra)
            s = [v + self.TITLE_W * sum(self.bm.idf.get(x, 0) for x in want & tt[i]) for i, v in enumerate(s)]
        if law:                                                   # 법령을 지정하면 그 법령만
            keep = set(self.by_law.get(norm_law(law), []))
            s = [v if i in keep else 0 for i, v in enumerate(s)]
        order = sorted(range(len(s)), key=lambda i: -s[i])
        sim = self._query_sim(query)
        if sim is not None:                                       # 낱말(BM25) 순위 + 임베딩 순위 섞기(RRF, 순위만 씀)
            if law: sim = [v if i in keep else -1 for i, v in enumerate(sim)]
            eo = sorted(range(len(sim)), key=lambda i: -sim[i])[:self.POOL]
            rrf = {}
            for r, i in enumerate(order[:self.POOL]): rrf[i] = rrf.get(i, 0) + 1 / (60 + r)
            for r, i in enumerate(eo): rrf[i] = rrf.get(i, 0) + self.EMB_W / (60 + r)
            order = sorted(rrf, key=lambda i: -rrf[i])
        top = s[order[0]] if order else 0
        floor = min_score if min_score is not None else max(4.0, 1.2 * len(q))   # 너무 약하면 '못 찾음' (평가로 정한 값)
        out, cites = [], set()
        for i in order:
            c = self.C[i]
            if self.ONE_PER_CITE and c['cite'] in cites: continue      # 같은 인용(같은 조·같은 별표 소제목)은 한 번만 — 다른 조문에 자리를 줌
            if c['status'] == '시행 전' and not include_future: continue
            sem = sim is not None and self.sim_min is not None and sim[i] >= self.sim_min   # 뜻이 충분히 가까움 (낱말이 달라도)
            if sim is None and s[i] < floor: break
            # 포함률 = 조각에 있는 질문 단어의 희귀도 합 / 질문 단어 희귀도 합. 법령 원문에 아예 없는 단어(아이폰 등)는 가장 무겁게 셈
            w = {t: self.bm.idf.get(t, self._max_idf) for t in qs}
            has = [t for t in qs if t in self.tokset[i] or any(y in self.tokset[i] for y in alt[t])]   # 같은 뜻 낱말이 있어도 들어 있는 것으로
            cover = sum(w[t] for t in has) / sum(w.values())
            if cover < cover_need and not sem: continue
            if sim is not None and s[i] < floor and not sem: continue
            out.append({**c, 'score': round(float(s[i]), 2), 'cover': round(cover, 2),
                        'sim': round(float(sim[i]), 3) if sim is not None else None}); cites.add(c['cite'])
            if len(out) >= k: break
        return out

    # ---------- 화면에 줄 답 ----------
    def answer(self, query=None, refs=None, k=3, include_future=False):
        """refs(대응표의 조항 글)가 있으면 그 조문을, 없으면 검색 결과를 인용. 시행 전 판이 따로 있으면 알려 줌"""
        found, route = [], None
        if refs:                                       # refs = [(법령 이름, '제32조~제35조, 제143조'), …] 또는 '도로교통법 제32조' 같은 글
            pairs = [(l, a) for l, s in refs for a in arts_in(s)] if isinstance(refs, list) else self.parse_refs(refs)
            for law, art in pairs:
                found += self.article(law, art, include_future)
            route = '대응표'
        if not found and query:
            found = self.search(query, k=k, include_future=include_future); route = '검색'
        if not found:
            return {'route': route, 'result': NOT_FOUND, 'items': []}
        items, seen = [], set()
        for c in found:
            if c['chunk_id'] in seen: continue
            seen.add(c['chunk_id'])
            future = [x for x in self.article(c['law_name'], c['article'], True) if x['status'] == '시행 전'] if c.get('article') else []
            items.append({'cite': c['cite'], 'law_name': c['law_name'], 'law_no': c.get('law_no'), 'article': c.get('article'),
                          'article_title': c.get('article_title'), 'para': c.get('para'), 'section': c.get('section'), 'annex': c.get('annex'),
                          'effective': c.get('effective'), 'doc_type': c.get('group'), 'status': ('참고 자료(법령 아님)' if c.get('group') == '정책자료' else c['status']), 'quote': c['text'], 'score': c.get('score'), 'cover': c.get('cover'),
                          'future_version': future[0]['cite'] if future and c['status'] == '시행 중' else None})
        return {'route': route, 'result': '찾음', 'items': items[:max(k, len(items) if route == '대응표' else k)]}
