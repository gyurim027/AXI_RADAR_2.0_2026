import test from 'node:test';
import assert from 'node:assert/strict';
import { MARGIN, placeBubble } from '../src/user/components/placeBubble.js';

const vp = { width: 1240, height: 700 };
const size = { width: 360, height: 80 };

test('여유가 있으면 아이콘 아래 왼쪽 맞춤이다', () => {
  const p = placeBubble({ top: 100, bottom: 128, left: 200 }, size, vp);
  assert.deepEqual(p, { top: 132, left: 200, flipped: false });
});

test('오른쪽 가장자리에서는 왼쪽으로 민다', () => {
  const p = placeBubble({ top: 20, bottom: 48, left: 1200 }, size, vp);
  assert.equal(p.left, vp.width - size.width - MARGIN);
});

test('왼쪽 가장자리에서는 여백만큼 민다', () => {
  assert.equal(placeBubble({ top: 20, bottom: 48, left: 2 }, size, vp).left, MARGIN);
});

test('아래가 모자라면 위로 뒤집는다', () => {
  const p = placeBubble({ top: 640, bottom: 668, left: 300 }, size, vp);
  assert.equal(p.flipped, true);
  assert.equal(p.top, 640 - 4 - size.height);
});

test('위도 모자라면 아래에 둔다', () => {
  const p = placeBubble({ top: 30, bottom: 58, left: 300 }, { width: 360, height: 700 }, vp);
  assert.equal(p.flipped, false);
});

test('화면보다 넓은 말풍선도 여백 안으로 모은다', () => {
  assert.equal(placeBubble({ top: 20, bottom: 48, left: 500 }, { width: 2000, height: 40 }, vp).left, MARGIN);
});
