import { useLayoutEffect, useState } from 'react';
import { isCenterFirstColumn } from '../utils/firstColumn.js';

/** 그려진 표의 첫 열 글자를 읽어 첫 열을 가운데로 둘지 정한다. 첫 열이 JSX(배지·화살표)여도 글자만 센다. */
export default function useFirstColumnCenter(tbodyRef, rows) {
  const [center, setCenter] = useState(true);
  useLayoutEffect(() => {
    const tbody = tbodyRef.current;
    if (!tbody) return;
    const texts = [...tbody.querySelectorAll(':scope > tr > td:first-child')].filter((td) => td.colSpan <= 1).map((td) => td.textContent);
    setCenter(isCenterFirstColumn(texts));
  }, [tbodyRef, rows]);
  return center;
}
