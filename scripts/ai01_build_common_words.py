"""AI-01 흔한 낱말 목록 만들기 (한 번, 또는 민원 원본이 크게 바뀔 때).

이름 찾기 모델이 일반 낱말(예: 소홀, 허송세월)을 이름으로 잘못 보는 것을 거르려고,
'모델이 이름이라고 본 낱말 중 서로 다른 일반 민원 5건 넘게 나오는 낱말' 목록을 만든다.
- 원문은 이 스크립트 안 메모리에서만 쓴다. 결과 파일에는 낱말만 한 줄에 하나씩 쓴다.
- 결과는 민원에서 나온 것이라 저장소에 올리지 않는다: data/private/ 또는 서버의 별도 위치에 두고
  .env의 AI01_COMMON_WORDS에 경로를 적는다.

실행 (선택 묶음 ai01 필요):
    uv run python scripts/ai01_build_common_words.py <민원 원본 폴더> data/private/ai01_common_words.txt
원본 폴더: 성남데이터넷 '민원 상세정보 현황' 월별 xlsx가 연도 폴더별로 든 곳
"""
from __future__ import annotations

import collections
import glob
import os
import re
import sys

from app.services.ai01 import masking

MIN_DOCS = 5


def general_texts(folder: str) -> list[str]:
    import openpyxl
    texts = {}
    for f in sorted(glob.glob(os.path.join(folder, "*", "*.xlsx"))):
        if re.search(r"-\d{14}\.xlsx$", f):                      # 내려받은 시각 이름의 중복 파일은 뺀다
            continue
        for i, r in enumerate(openpyxl.load_workbook(f, read_only=True).active.iter_rows(values_only=True)):
            if i == 0:
                continue
            title, body = str(r[1] or ""), str(r[5] or "")
            if re.search(r"SPP-\d{4}-[0-9A-Z]+", title) or title.startswith("스마트국민제보"):
                continue                                         # 일반 민원만
            t = masking.preprocess(title, body)
            texts.setdefault(re.sub(r"\s+", "", t)[:200], t)     # 같은 글을 여러 번 올린 민원은 한 번만
    return list(texts.values())


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    folder, out = sys.argv[1], sys.argv[2]
    texts = general_texts(folder)
    print(f"일반 민원(같은 글 한 번) {len(texts):,}건", flush=True)
    ner = masking._ner()
    cands = set()
    for i, t in enumerate(texts, 1):
        t = masking.rule_mask(t, collections.Counter())
        for start in range(0, max(len(t), 1), 400):
            for e in ner(t[start:start + 450]):
                w = re.sub(r"\s", "", e.get("word", ""))
                if e.get("entity_group") == "NAME" and re.fullmatch(r"[가-힣]{2,4}", w):
                    cands.add(w)
        if i % 1000 == 0:
            print(f"   {i:,}건 …", flush=True)
    common = sorted(w for w in cands if sum(1 for t in texts if w in t) > MIN_DOCS)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(common) + "\n")
    print(f"이름 후보 {len(cands):,}개 중 흔한 낱말 {len(common):,}개 → {out}")


if __name__ == "__main__":
    main()
