import test from 'node:test';
import assert from 'node:assert/strict';
import { DEFAULT_STATE, limits, nextByKey, resolveRatio, trackFractions, isValidState, TABLE_MIN_PX, MAP_MIN_PX } from '../src/user/features/candidates/split.js';

const W = 1400;

test('허용 범위는 표 480px, 지도 320px을 지킨다', () => {
  const { min, max } = limits(W);
  assert.ok(Math.abs(min * W - TABLE_MIN_PX) < 1e-6);
  assert.ok(Math.abs((1 - max) * W - MAP_MIN_PX) < 1e-6);
});

test('좁은 화면에서는 5:5 근처로 모인다', () => {
  const { min, max } = limits(800);
  assert.ok(min <= 0.5 && max >= 0.5);
});

test('범위 안에서 끌면 그 비율이 된다', () => {
  assert.deepEqual(resolveRatio(0.55, W), { mode: 'split', ratio: 0.55 });
});

test('범위를 조금 넘기면 한도에 멈추고, 한참 넘기면 접힌다', () => {
  const { min, max } = limits(W);
  const low = resolveRatio(min - 0.01, W);
  assert.equal(low.mode, 'split');
  assert.ok(Math.abs(low.ratio - min) < 1e-3);
  assert.equal(resolveRatio(0.1, W).mode, 'map');
  const high = resolveRatio(max + 0.01, W);
  assert.equal(high.mode, 'split');
  assert.ok(Math.abs(high.ratio - max) < 1e-3);
  assert.equal(resolveRatio(0.98, W).mode, 'table');
});

test('방향키: 한 칸씩 움직이고 접힌 쪽에서는 다시 펼친다', () => {
  const s = { mode: 'split', ratio: 0.6 };
  assert.equal(nextByKey(s, 'ArrowLeft', W).ratio, 0.56);
  assert.equal(nextByKey(s, 'ArrowRight', W).ratio, 0.64);
  assert.equal(nextByKey({ mode: 'table', ratio: 0.6 }, 'ArrowLeft', W).mode, 'split');
  assert.equal(nextByKey({ mode: 'map', ratio: 0.6 }, 'ArrowRight', W).mode, 'split');
  assert.equal(nextByKey({ mode: 'map', ratio: 0.6 }, 'ArrowLeft', W), null);
});

test('Home은 표를 접고 End는 지도를 접고 Enter는 기본 비율로 돌린다', () => {
  const s = { mode: 'split', ratio: 0.5 };
  assert.equal(nextByKey(s, 'Home', W).mode, 'map');
  assert.equal(nextByKey(s, 'End', W).mode, 'table');
  assert.deepEqual(nextByKey(s, 'Enter', W), DEFAULT_STATE);
  assert.equal(nextByKey(s, 'a', W), null);
});

test('칸 비율: 기본 6:4, 접힌 쪽은 0', () => {
  assert.deepEqual(trackFractions(DEFAULT_STATE), { left: 60, right: 40 });
  assert.deepEqual(trackFractions({ mode: 'table', ratio: 0.6 }), { left: 1, right: 0 });
  assert.deepEqual(trackFractions({ mode: 'map', ratio: 0.6 }), { left: 0, right: 1 });
});

test('저장값 검증: 이상한 값은 기본 비율로 돌아간다', () => {
  assert.equal(isValidState({ mode: 'split', ratio: 0.5 }), true);
  assert.equal(isValidState({ mode: 'x', ratio: 0.5 }), false);
  assert.equal(isValidState({ mode: 'split', ratio: 5 }), false);
  assert.equal(isValidState(null), false);
});
