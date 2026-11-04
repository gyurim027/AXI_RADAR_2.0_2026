import { useSyncExternalStore } from 'react';

// 표 밀도 (UX 고도화 A-4, D-8). 'normal'(기본 간격)과 'compact'(촘촘히) 기능은 남겨 두되,
// 화면의 선택 버튼은 숨겼고(soft 삭제, 규림님 결정 11/04) 늘 'normal'로 보인다.
// 버튼을 다시 보이려면 DENSITY_PICKER_VISIBLE을 true로 바꾸고, 저장값(촘촘히) 읽기도 함께 켠다.
export const DENSITY_PICKER_VISIBLE = false;
const KEY = 'radar.admin.density';
const listeners = new Set();

function read() {
  if (!DENSITY_PICKER_VISIBLE) return 'normal'; // 이전에 촘촘히를 골라 저장한 브라우저도 기본 간격으로 보인다
  try {
    return window.localStorage.getItem(KEY) === 'compact' ? 'compact' : 'normal';
  } catch {
    return 'normal';
  }
}
let current = read();

export function setDensity(value) {
  current = value === 'compact' ? 'compact' : 'normal';
  try {
    window.localStorage.setItem(KEY, current);
  } catch {
    /* 저장하지 못해도 이번 화면에서는 바뀐다 */
  }
  listeners.forEach((l) => l());
}

const subscribe = (fn) => {
  listeners.add(fn);
  return () => listeners.delete(fn);
};

/** 'normal'(기본 간격, 기본값) 또는 'compact'(촘촘히) */
export const useDensity = () => useSyncExternalStore(subscribe, () => current, () => 'normal');
