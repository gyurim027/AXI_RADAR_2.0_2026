import { useSyncExternalStore } from 'react';

// 표 밀도 (UX 고도화 A-4, D-8). 두 가지를 두고 촘촘히를 기본으로 한다. 고른 값은 이 브라우저에만 남긴다.
const KEY = 'radar.admin.density';
const listeners = new Set();

function read() {
  try {
    return window.localStorage.getItem(KEY) === 'normal' ? 'normal' : 'compact';
  } catch {
    return 'compact';
  }
}
let current = read();

export function setDensity(value) {
  current = value === 'normal' ? 'normal' : 'compact';
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

/** 'compact'(촘촘히, 기본) 또는 'normal'(기본 간격) */
export const useDensity = () => useSyncExternalStore(subscribe, () => current, () => 'compact');
