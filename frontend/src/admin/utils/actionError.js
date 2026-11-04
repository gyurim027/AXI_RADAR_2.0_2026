// 저장·요청이 실패했을 때 어드민 화면 맨 위 안내 띠를 띄운다. 오류 문구는 공통 규칙 12번 말투를 따른다.
// message를 주면 그 문구를, 안 주면 공통 문구를 보인다.
const EVENT = 'radar-admin-action-error';

export function reportActionError(message) {
  window.dispatchEvent(new CustomEvent(EVENT, { detail: { message: typeof message === 'string' ? message : '' } }));
}
export function onActionError(handler) {
  const listener = (e) => handler(e.detail?.message || '');
  window.addEventListener(EVENT, listener);
  return () => window.removeEventListener(EVENT, listener);
}
