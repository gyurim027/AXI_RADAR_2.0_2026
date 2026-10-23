"""AI-05 법령 RAG ① 원문 글자 뽑기 — hwp(HWP5) · hwpx · pdf → 글자 + 문서 정보
외부 프로그램 없이 동작(pdf만 poppler의 pdftotext 사용). 실행: python -m app.services.ai05.extract <원문 폴더> <출력 jsonl>
"""
import json, re, struct, subprocess, sys, zipfile, zlib
from pathlib import Path
import olefile

# ---------- HWP5 (한글 2002 이후 .hwp) ----------
PARA_TEXT = 67                      # HWPTAG_BEGIN(16) + 51 : 문단 글자 레코드
ONE_UNIT = {0, 10, 13} | set(range(24, 32))   # 글자 1칸짜리 제어 문자 (10 줄바꿈, 13 문단 끝)

def _records(data):
    """BodyText 섹션을 레코드(tag, payload)로 나눔"""
    i = 0
    while i + 4 <= len(data):
        h, = struct.unpack_from('<I', data, i); i += 4
        tag, size = h & 0x3FF, (h >> 20) & 0xFFF
        if size == 0xFFF:
            size, = struct.unpack_from('<I', data, i); i += 4
        yield tag, data[i:i + size]; i += size

def _para_text(p):
    """문단 글자(UTF-16LE)에서 표·그림 같은 제어 문자(8칸)를 건너뛰고 글자만 남김"""
    out, i, n = [], 0, len(p) // 2
    while i < n:
        c, = struct.unpack_from('<H', p, i * 2)
        if c < 32:
            if c in (10, 13): out.append('\n')
            elif c == 9: out.append('\t')
            i += 1 if c in ONE_UNIT else 8
            continue
        out.append(chr(c)); i += 1
    return ''.join(out)

def read_hwpml(path):
    """국가법령정보센터가 내려 주는 .hwp는 대부분 XML(HWPML 2.x) — <P> 안 <CHAR> 글자를 이음"""
    import html
    s = Path(path).read_text(encoding='utf-8', errors='replace')
    body = s[s.find('<BODY'):] if '<BODY' in s else s
    out = []
    for p in re.findall(r'<P\b[^>]*>(.*?)</P>', body, re.S):
        t = ''.join(re.findall(r'<CHAR>(.*?)</CHAR>', p, re.S))
        out.append(html.unescape(t.replace('&nbsp;', ' ')).rstrip())
    return '\n'.join(out)

def read_hwp(path):
    with open(path, 'rb') as fh:
        head = fh.read(5)
    if head == b'<?xml':
        return read_hwpml(path)
    if head[:2] == b'PK':
        return read_hwpx(path)
    ole = olefile.OleFileIO(str(path))
    flags, = struct.unpack_from('<I', ole.openstream('FileHeader').read(), 36)
    compressed, distributed = flags & 1, flags & 4
    if distributed:
        raise ValueError('배포용 문서(암호화)라 글자를 읽을 수 없음')
    secs = sorted((e for e in ole.listdir() if e[0] == 'BodyText'), key=lambda e: int(e[1][7:]))
    texts = []
    for e in secs:
        raw = ole.openstream(e).read()
        data = zlib.decompress(raw, -15) if compressed else raw
        texts += [_para_text(p) for tag, p in _records(data) if tag == PARA_TEXT]
    return '\n'.join(t.rstrip('\n') for t in texts)

# ---------- HWPX (zip + xml) ----------
def read_hwpx(path):
    z = zipfile.ZipFile(path); out = []
    for n in sorted(x for x in z.namelist() if re.match(r'Contents/section\d+\.xml', x)):
        xml = z.read(n).decode('utf-8')
        for para in re.findall(r'<hp:p\b.*?</hp:p>', xml, re.S):
            out.append(''.join(re.findall(r'<hp:t>(.*?)</hp:t>', para, re.S)))
    return '\n'.join(out).replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')

# ---------- PDF ----------
def read_pdf(path):
    return subprocess.run(['pdftotext', '-enc', 'UTF-8', str(path), '-'], capture_output=True, text=True, check=True).stdout

READERS = {'.hwp': read_hwp, '.hwpx': read_hwpx, '.pdf': read_pdf}

# ---------- 파일 이름 → 문서 정보 ----------
# 국가법령정보센터 파일 이름 꼴: 이름(구분)(제N호)(YYYYMMDD).hwp
NAME = re.compile(r'^(?P<name>.+?)\((?P<kind>[^()]+)\)\((?P<no>제[^()]+호)\)\((?P<date>\d{8})\)$')
FOLDER_KIND = {'국가법령정보센터_현행법령': '법령', '국가법령정보센터_행정규칙': '행정규칙', '국가법령정보센터_자치법규': '자치법규', '정책자료': '정책자료'}

# 국가법령정보센터 꼴이 아닌 파일 이름 → (법령 이름, 시행일). 같은 지침의 개정전문 등을 한 이름으로 묶음
ALIAS = {
    '(개정전문) 도로안전시설 설치 및 관리지침 일부개정 (26.08.14)': ('도로안전시설 설치 및 관리 지침', '2026-08-14'),
    '(250625) 교통정온화 시설 설치 및 관리지침 개정전문': ('교통정온화 시설 설치 및 관리지침', '2025-07-01'),
    '보도설치 및 관리지침 개정전문': ('보도 설치 및 관리 지침', '2021-07-23'),
}
NAME_FIX = {'도로법시행규칙': '도로법 시행규칙', '도로법 시행규칙_현행서식': '도로법 시행규칙', '1': '성남시 사무위임 조례'}

def doc_info(path):
    info = _doc_info(path)
    if path.stem in ALIAS:
        info['law_name'], info['effective'] = ALIAS[path.stem]
    info['law_name'] = NAME_FIX.get(info['law_name'], info['law_name'])
    return info

def _doc_info(path):
    stem = path.stem; m = NAME.match(stem)
    info = {'file': path.name, 'folder': path.parent.name, 'group': FOLDER_KIND.get(path.parent.name, '기타'),
            'law_name': stem, 'law_kind': None, 'law_no': None, 'effective': None}
    if m:
        d = m['date']
        info.update(law_name=m['name'].strip(), law_kind=m['kind'], law_no=m['no'], effective=f'{d[:4]}-{d[4:6]}-{d[6:]}')
    else:
        # 예: [별표 1] 제목(제2조제1항 관련)(법령 이름) — 마지막 괄호 = 법령 이름
        b = re.match(r'^\[(별[표지첨][^\]]*)\]\s*(.+?)\(([^()]+)\)(?:\s*\(\d+\))?$', stem)
        if b: info.update(law_name=b[3].strip(), annex=b[1].strip(), annex_title=b[2].strip())
    return info

def main(src, out):
    src = Path(src); n = bad = 0
    with open(out, 'w', encoding='utf-8') as f:
        for p in sorted(src.rglob('*')):
            if not p.is_file() or p.suffix.lower() not in READERS or p.parent.name not in FOLDER_KIND: continue
            info = doc_info(p)
            try:
                text = READERS[p.suffix.lower()](p)
            except Exception as e:
                info['error'] = str(e); text = ''; bad += 1
            info['chars'] = len(text)
            f.write(json.dumps({**info, 'text': text}, ensure_ascii=False) + '\n'); n += 1
    print(f'문서 {n}개 · 못 읽음 {bad}개 → {out}')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
