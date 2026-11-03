/**
 * 표 첫 열 정렬 규칙 (규림님이 정했다, 11/04): 본문 칸이 모두 3자 이하이면 첫 열을 가운데,
 * 하나라도 4자 이상이면 그 표의 첫 열은 모두 왼쪽. 숫자로만 된 칸은 길이와 상관없이 3자 이하로 본다.
 */
const NUMERIC = /^[0-9][0-9,.]*$/;

export function isCenterFirstColumn(texts) {
  return texts.every((raw) => {
    const t = String(raw ?? '').trim();
    return NUMERIC.test(t) || [...t].length <= 3;
  });
}
