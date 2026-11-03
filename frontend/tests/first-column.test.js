import test from 'node:test';
import assert from 'node:assert/strict';
import { isCenterFirstColumn } from '../src/shared/utils/firstColumn.js';

test('숫자로만 된 칸은 길이와 상관없이 가운데로 본다', () => {
  assert.equal(isCenterFirstColumn(['1', '12345', '1,234.5']), true);
});
test('3자 이하 글자는 가운데로 본다', () => {
  assert.equal(isCenterFirstColumn(['수정구', '중원구', '분당구']), true);
});
test('4자 이상 글자가 하나라도 있으면 왼쪽으로 본다', () => {
  assert.equal(isCenterFirstColumn(['JUR-01', 'JUR-02']), false);
  assert.equal(isCenterFirstColumn(['수정구', '대시보드']), false);
});
test('숫자와 글자가 섞여도 글자가 4자 이상이면 왼쪽으로 본다', () => {
  assert.equal(isCenterFirstColumn(['1', '12345', '2026년 하반기']), false);
});
test('칸이 없으면 가운데로 둔다', () => {
  assert.equal(isCenterFirstColumn([]), true);
});
