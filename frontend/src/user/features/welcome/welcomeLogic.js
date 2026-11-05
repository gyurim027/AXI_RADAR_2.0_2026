/** 소개 모달을 열지 정한다. 로그인한 사용자가 있고, 이동할 때 welcome 표시를 받았을 때만 연다. */
export function shouldOpenWelcome(state, user) {
  return Boolean(user) && state?.welcome === true;
}

/** 단계 번호를 0 ~ (개수-1) 안으로 맞춘다. */
export function clampStep(index, count) {
  if (count <= 0) return 0;
  return Math.min(Math.max(index, 0), count - 1);
}
