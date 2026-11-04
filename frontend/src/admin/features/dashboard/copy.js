// AD-01 대시보드 문구 (10_3_화면명세_어드민 AD-01)

export const DASH = {
  title: '대시보드',
  subtitle: '지금 회차가 어디까지 왔는지와 다음에 할 일을 봅니다.',
  noRun: '진행 중인 회차가 없습니다',
  runTitle: (name) => `${name || '-'} 회차`,
  next: (task) => `다음에 할 일: ${task}`,
  goto: (screen) => `${screen} 열기`,
  todoTitle: '처리할 일',
  baseTitle: '기준 현황',
  dataTitle: '자료 최신 여부',
  runsTitle: '최근 수집·산정 실행',
  approvalsTitle: '승인 현황',
  regTitle: '규정 변경',
  criteriaTitle: '산정 기준',
  // 카드 오른쪽 위 상태와 아래 '보기' 링크 (UX 고도화 A-1)
  state: { ok: '정상', check: '확인 필요', fail: '실패 있음', wait: '승인 대기 있음', none: '대기 없음', current: '현재 버전', unknown: '-' },
  more: {
    data: '자료 목록 보기',
    runs: '실행 기록 보기',
    approvals: '승인 이력 보기',
    regs: '규정 변경 보기',
    criteria: '산정 기준 보기',
    checks: '검사 결과 보기',
  },
  checksTitle: '자료 검사', // 제안 문구: 정의서 AD-01에 이 카드 이름이 없다
  criteriaCurrent: '현재 버전',
  criteriaPending: '승인 대기',
  runsEmpty: '아직 실행한 기록이 없습니다. 회차 목록에서 산정을 시작해 주세요.', // E-4
  failed: '대시보드를 불러오지 못했습니다.',
};
