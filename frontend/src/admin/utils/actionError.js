// 저장·요청이 실패했을 때 어드민 화면 맨 위 안내 띠를 띄운다. 오류 문구는 공통 규칙 12번 말투를 따른다.
const EVENT = 'radar-admin-action-error';

export function reportActionError() {
  window.dispatchEvent(new CustomEvent(EVENT));
}
export function onActionError(handler) {
  window.addEventListener(EVENT, handler);
  return () => window.removeEventListener(EVENT, handler);
}
