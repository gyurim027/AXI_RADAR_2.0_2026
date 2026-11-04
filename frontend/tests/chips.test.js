import test from 'node:test';
import assert from 'node:assert/strict';
import { conditionChips, MAX_CONDITION_CHIPS } from '../src/user/features/candidates/chips.js';

const map = {
  result: { id: 'result', name: '종합 조건' },
  hazard: { id: 'hazard', name: '위험 조건' },
  exposure: { id: 'exposure', name: '노출 조건' },
  vulnerable: { id: 'vulnerable', name: '취약 조건' },
};

test('칩 이름은 짧고 전체 이름은 따로 담는다', () => {
  const { shown } = conditionChips({ conditions: ['result'] }, map);
  assert.deepEqual(shown, [{ id: 'result', label: '종합', full: '종합 조건', tone: 'accent' }]);
});

test('조건마다 색이 다르다', () => {
  const { shown } = conditionChips({ conditions: ['result', 'hazard', 'exposure'] }, map);
  assert.equal(new Set(shown.map((c) => c.tone)).size, 3);
});

test('3개를 넘으면 나머지는 숨긴 목록에 담는다', () => {
  const { shown, hidden } = conditionChips({ conditions: ['result', 'hazard', 'exposure', 'vulnerable'] }, map);
  assert.equal(shown.length, MAX_CONDITION_CHIPS);
  assert.deepEqual(hidden.map((c) => c.label), ['취약']);
});

test('조건 정의에 없는 값은 건너뛰고, 없으면 빈 목록이다', () => {
  const { shown, hidden } = conditionChips({ conditions: ['zzz'] }, map);
  assert.deepEqual(shown, []);
  assert.deepEqual(hidden, []);
  assert.deepEqual(conditionChips({}, map).shown, []);
});
