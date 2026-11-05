/**
 * 소개 모달을 어떻게 열지 정한다.
 * - 'replay': 로그인한 사용자가 메뉴의 `소개`로 연 경우(이동할 때 welcome 표시를 받음)
 * - 'prelogin': 로그인 화면이고 이 탭에서 아직 닫은 적이 없는 경우
 * - null: 열지 않는다
 */
export function welcomeMode({ state, user, pathname, seenThisTab }) {
  if (user) return state?.welcome === true ? 'replay' : null;
  return pathname === '/login' && !seenThisTab ? 'prelogin' : null;
}

/** 단계 번호를 0 ~ (개수-1) 안으로 맞춘다. */
export function clampStep(index, count) {
  if (count <= 0) return 0;
  return Math.min(Math.max(index, 0), count - 1);
}
