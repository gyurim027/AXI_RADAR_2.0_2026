// 점검 후보 화면의 표·지도 분할. 기본은 표 6 : 지도 4(디자인 시스템 9-2)이고, 끌어서 바꾸거나 한쪽을 접을 수 있다.
export const DEFAULT_RATIO = 0.6;
export const TABLE_MIN_PX = 480;
export const MAP_MIN_PX = 320;
export const KEY_STEP = 0.04;
const STORAGE_KEY = 'radar.candidates.split';
export const DEFAULT_STATE = { mode: 'split', ratio: DEFAULT_RATIO };

/** 표 몫(0~1)의 허용 범위. 화면이 좁으면 5:5 근처로 모인다. */
export function limits(width) {
  const w = Math.max(width || 0, 1);
  return { min: Math.min(TABLE_MIN_PX / w, 0.5), max: Math.max(1 - MAP_MIN_PX / w, 0.5) };
}

/** 끌어서 놓은 자리(표 몫)를 상태로 바꾼다. 허용 범위를 한참 넘기면 그쪽을 접는다. */
export function resolveRatio(raw, width) {
  const { min, max } = limits(width);
  if (raw < min * 0.7) return { mode: 'map', ratio: min };
  if (raw > max + (1 - max) * 0.5) return { mode: 'table', ratio: max };
  // 키로 한 칸씩 움직일 때 0.56이 0.5599999처럼 어긋나지 않게 소수 넷째 자리에서 맞춘다.
  return { mode: 'split', ratio: Math.round(Math.min(max, Math.max(min, raw)) * 10000) / 10000 };
}

/** 분할 막대에서 누른 키가 만드는 상태. 해당 없는 키는 null. */
export function nextByKey(state, key, width) {
  const { min, max } = limits(width);
  if (key === 'Enter') return DEFAULT_STATE;
  if (key === 'Home') return { mode: 'map', ratio: state.ratio };
  if (key === 'End') return { mode: 'table', ratio: state.ratio };
  if (key === 'ArrowLeft') {
    if (state.mode === 'table') return { mode: 'split', ratio: max };
    if (state.mode === 'map') return null;
    return resolveRatio(state.ratio - KEY_STEP, width);
  }
  if (key === 'ArrowRight') {
    if (state.mode === 'map') return { mode: 'split', ratio: min };
    if (state.mode === 'table') return null;
    return resolveRatio(state.ratio + KEY_STEP, width);
  }
  return null;
}

/** 그리드 칸 비율. 접힌 쪽은 0이다. */
export function trackFractions({ mode, ratio }) {
  if (mode === 'table') return { left: 1, right: 0 };
  if (mode === 'map') return { left: 0, right: 1 };
  return { left: +(ratio * 100).toFixed(2), right: +((1 - ratio) * 100).toFixed(2) };
}

export function isValidState(v) {
  return !!v && ['split', 'table', 'map'].includes(v.mode) && typeof v.ratio === 'number' && v.ratio > 0.1 && v.ratio < 0.9;
}

/** 이 브라우저에만 기억한다. 저장소를 못 써도 기본 비율로 정상 동작한다. */
export function readStoredState() {
  try {
    const v = JSON.parse(window.localStorage.getItem(STORAGE_KEY));
    return isValidState(v) ? { mode: v.mode, ratio: v.ratio } : DEFAULT_STATE;
  } catch {
    return DEFAULT_STATE;
  }
}

export function writeStoredState(state) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* 저장하지 못해도 화면은 계속 쓴다 */
  }
}
