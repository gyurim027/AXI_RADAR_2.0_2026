"""AI-05 법령 RAG ② 조문 자르기 — 조(·항) 단위, 조문이 없는 지침·별표는 제목 기준 묶음
실행: python -m app.services.ai05.chunk data/ai05/docs.jsonl data/ai05/chunks.jsonl [기준일 YYYY-MM-DD]
"""
import json, re, sys, datetime

ART = re.compile(r'(?m)^[ \t]*(제\d+조(?:의\d+)?)[ \t]*\(([^)\n]{0,40})\)')    # 제10조(보도의 설치) / 제3조의2(…)
CHAPTER = re.compile(r'(?m)^[ \t]*(제\d+장(?:의\d+)?[ \t]+\S.*)$')
ADDENDA = re.compile(r'(?m)^[ \t]*부[ \t]*칙')                                  # 부칙 시작
HANG = re.compile(r'(?=[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳])')
# 제목 줄: '제1장 총칙' · '제 3 장' · '1. 총칙' · '3.2 보도의 폭' · '3-2 유효폭' · '가. 설치기준' (표 안 숫자 '30 이하'는 제외)
HEAD = re.compile(r'^[ \t]*((?:제[ \t]*\d+[ \t]*[장절편][^\n]{0,40})|(?:\d{1,2}(?:\.|(?:[.\-]\d{1,2}){1,3}\.?)[ \t]*[가-힣][^\n]{0,40})|(?:[가-하]\.[ \t]+[가-힣][^\n]{1,40}))$')
MAX_ART, WIN = 1800, 900          # 조 하나가 이보다 길면 항으로 나눔 / 지침은 약 900자씩

def clean(t):
    return re.sub(r'[ \t]+', ' ', re.sub(r'\n{3,}', '\n\n', t)).strip()

def by_article(text):
    """조문형 문서: (장, 조번호, 조제목, 부칙 여부, 본문) 목록"""
    cut = ADDENDA.search(text); add_at = cut.start() if cut else len(text)
    ms = list(ART.finditer(text)); out = []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        chap = [c.group(1).strip() for c in CHAPTER.finditer(text, 0, m.start())]
        out.append((chap[-1] if chap and m.start() < add_at else None, m.group(1), m.group(2).strip(),
                    m.start() >= add_at, text[m.start():end]))
    return out

def by_heading(text):
    """조문이 없는 문서: 제목 줄을 만날 때마다 구역을 바꾸고 약 900자씩 묶음"""
    out, buf, sec, cur = [], [], None, None
    for line in text.split('\n'):
        h = HEAD.match(line)
        if h and buf and sum(map(len, buf)) > 200:
            out.append((cur, '\n'.join(buf))); buf = []
        if h: sec = h.group(1).strip()
        if not buf: cur = sec
        buf.append(line)
        if sum(map(len, buf)) > WIN:
            out.append((cur, '\n'.join(buf))); buf = []
    if buf: out.append((cur, '\n'.join(buf)))
    return [(s, t) for s, t in out if len(clean(t)) >= 30]

def chunks_of(doc, today):
    base = {k: doc.get(k) for k in ('file', 'group', 'law_name', 'law_kind', 'law_no', 'effective', 'annex', 'annex_title')}
    base['status'] = '시행 전' if doc.get('effective') and doc['effective'] > today else '시행 중'
    text = doc['text']; arts = by_article(text) if not doc.get('annex') else []
    first = ART.search(text)
    # 조문형 = 조가 3개 이상이고 본문 앞부분(30% 안)부터 시작. 지침 끝 부칙에만 '제N조'가 있으면 제목형으로 자름
    if len(arts) >= 3 and first and first.start() < 0.3 * len(text):
        for chap, no, title, addenda, body in arts:
            parts = [body] if len(body) <= MAX_ART else [p for p in HANG.split(body) if p.strip()]
            for j, p in enumerate(parts):
                para = re.match(r'[①-⑳]', p.strip())
                yield {**base, 'chapter': chap, 'article': no, 'article_title': title, 'addenda': addenda,
                       'para': para.group(0) if para and j else None,
                       'text': clean(p if j == 0 or not para else f'{no}({title}) ' + p)}
    else:
        for sec, body in by_heading(text):
            yield {**base, 'chapter': None, 'article': None, 'article_title': None, 'addenda': False,
                   'para': None, 'section': sec, 'text': clean(body)}

def cite(c):
    """사람이 읽는 출처: 법령명 제10조(제목) ② · 별표 1 · 구역 이름 + 시행일"""
    s = c['law_name']
    if c.get('annex'): s += f" [{c['annex']}]"
    if c.get('article'): s += f" {'부칙 ' if c.get('addenda') else ''}{c['article']}({c['article_title']})" + (f" {c['para']}" if c.get('para') else '')
    elif c.get('section'): s += f" '{c['section']}'"
    if c.get('effective'): s += f" · 시행 {c['effective']}"
    return s + (' · 시행 전' if c['status'] == '시행 전' else '')

def main(src, out, today=None):
    today = today or datetime.date.today().isoformat(); n = 0
    docs = [json.loads(l) for l in open(src, encoding='utf-8')]
    # 같은 법령·같은 시행일·같은 별표가 두 파일이면(hwp와 개정전문 pdf 등) 글자가 많은 쪽만 씀
    best = {}
    for i, d in enumerate(docs):
        k = (d['law_name'], d.get('effective'), d.get('annex'))
        if k not in best or d['chars'] > docs[best[k]]['chars']: best[k] = i
    keep = set(best.values())
    with open(out, 'w', encoding='utf-8') as f:
        for i, doc in enumerate(docs):
            if i not in keep: print('  같은 문서라 뺌:', doc['file']); continue
            for j, c in enumerate(chunks_of(doc, today)):
                c['chunk_id'] = f'L{i:03d}-{j:04d}'; c['cite'] = cite(c)
                f.write(json.dumps(c, ensure_ascii=False) + '\n'); n += 1
    print(f'조각 {n}개 (기준일 {today}) → {out}')

if __name__ == '__main__':
    main(*sys.argv[1:4])
