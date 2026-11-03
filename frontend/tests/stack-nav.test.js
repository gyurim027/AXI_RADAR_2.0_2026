import test from 'node:test';
import assert from 'node:assert/strict';
import { activeSection, singleFingerDragAllowed, wheelZoomAllowed } from '../src/user/features/candidates/stackNav.js';

test('협조 모드가 아니면 휠로 확대한다', () => {
  assert.equal(wheelZoomAllowed({ cooperative: false, ctrlKey: false, metaKey: false }), true);
});
test('협조 모드에서는 Ctrl이나 ⌘을 누른 때만 확대한다', () => {
  assert.equal(wheelZoomAllowed({ cooperative: true, ctrlKey: false, metaKey: false }), false);
  assert.equal(wheelZoomAllowed({ cooperative: true, ctrlKey: true, metaKey: false }), true);
  assert.equal(wheelZoomAllowed({ cooperative: true, ctrlKey: false, metaKey: true }), true);
});
test('터치 기기의 협조 모드에서는 한 손가락 끌기를 끈다', () => {
  assert.equal(singleFingerDragAllowed({ cooperative: true, coarse: true }), false);
  assert.equal(singleFingerDragAllowed({ cooperative: true, coarse: false }), true);
  assert.equal(singleFingerDragAllowed({ cooperative: false, coarse: true }), true);
});
test('보이는 높이가 더 큰 구역을 현재 구역으로 본다', () => {
  const sections = [
    { key: 'table', top: 0, bottom: 700 },
    { key: 'map', top: 700, bottom: 1200 },
  ];
  assert.equal(activeSection(sections, 0, 600), 'table');
  assert.equal(activeSection(sections, 500, 1100), 'map');
  assert.equal(activeSection([], 0, 600), null);
});
