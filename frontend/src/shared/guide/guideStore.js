// 안내 상태를 화면 여러 곳이 같이 본다: 안내를 보여 줄 수 있는 화면인지, 소개 모달이 열려 있는지.
const listeners = new Set();
const state = { available: false, welcomeOpen: false };

function emit() {
  listeners.forEach((l) => l());
}
export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
export const getAvailable = () => state.available;
export const getWelcomeOpen = () => state.welcomeOpen;

export function setAvailable(value) {
  if (state.available !== value) {
    state.available = value;
    emit();
  }
}
export function setWelcomeOpen(value) {
  if (state.welcomeOpen !== value) {
    state.welcomeOpen = value;
    emit();
  }
}

const START = 'radar:guide:start';
/** 상단의 `?` 버튼이 지금 화면 안내를 처음부터 다시 시작하게 한다. */
export function requestGuide() {
  window.dispatchEvent(new CustomEvent(START));
}
export function onGuideRequest(handler) {
  window.addEventListener(START, handler);
  return () => window.removeEventListener(START, handler);
}
