// 산정 묶음 문구 (10_3_화면명세_어드민 AD-06~AD-08). 기능정의서 문구가 바뀌면 이 파일만 고친다.

export const RUNS = {
  // AD-06
  title: '회차 목록',
  subtitle: '회차를 만들고 산정을 실행한 뒤 검토 중으로 엽니다.',
  create: '회차 만들기',
  head: ['회차', '종류', '상태', '산정 기준 버전', '민원 접수 기간', '생성일', '검토 시작일'],
  // 산정 중인 회차의 지금 단계. 그 단계에 할 버튼 하나만 진하게 보인다 (5-3 ③)
  noResult: '산정 결과 없음',
  stage: { before: '산정 전', running: '산정 실행 중', ready: '열기 전' },
  startCalc: '산정 시작하기',
  openRun: '검토 중으로 열기',
  empty: '아직 만든 회차가 없습니다. 회차를 만들어 주세요.',
  caption: '회차 목록',
  failedArea: '회차 목록',
  startFailed: '산정을 시작하지 못했습니다.',

  // 1-2 새 회차 창
  newTitle: '새 회차 만들기',
  newClose: '새 회차 창 닫기',
  kind: '종류',
  kinds: ['연간', '반기 참고'],
  name: '회차 이름',
  nameHelp: (annual, half) => `이름은 '${annual}'이나 '${half}'처럼 입력해 주세요.`,
  nameDuplicate: '같은 이름의 회차가 있습니다. 다른 이름을 적어 주세요.',
  // 1-2 민원 접수 기간 (정의서 v0.5.4, ISS-037)
  period: '민원 접수 기간',
  periodStart: '시작일',
  periodEnd: '끝일',
  periodHelp: '이 회차에서 쓸 민원이 접수된 기간입니다. 비워 두면 민원 없이 산정합니다. 산정을 시작하면 고칠 수 없습니다.',
  periodGaps: (months) => `이 기간에 민원 파일이 없는 달이 있습니다: ${months.join(', ')}. 이 달의 민원 없이 회차를 만들 수 있습니다.`,
  periodErrors: {
    periodBoth: '시작일과 끝일을 둘 다 적어 주세요.',
    periodOrder: '끝일은 시작일보다 빠를 수 없습니다.',
    periodFuture: '끝일은 오늘 이후로 정할 수 없습니다.',
  },
  fixPeriod: '민원 기간 고치기',
  fixPeriodTitle: '민원 접수 기간 고치기',
  fixPeriodClose: '민원 기간 고치기 창 닫기',
  periodLocked: '산정을 시작한 회차는 민원 접수 기간을 고칠 수 없습니다. 기간을 바꾸려면 새 회차를 만들어 주세요.', // ERR-50
  suggest: (year, kind) => (kind === '연간' ? `${year} 연간` : `${year} 상반기 참고`),

  // 2-1 회차 열기 확인 창
  openTitle: (name) => `${name} 회차를 검토 중으로 열까요?`,
  openClose: '회차 열기 창 닫기',
  openSub: '열면 시 도로과와 3개 구 도로관리팀 화면에 보이고 알림이 갑니다.',
  missingTitle: '빠진 자료',
  unratedTitle: '미평가 분야',
  refNote: '반기 참고 회차는 참고용으로만 볼 수 있으며, 점검 대상은 확정할 수 없습니다.',
  goMissing: '빠진 자료 올리기',
  notFinished: '산정이 끝나지 않아 열 수 없습니다.',
};

export const LOG = {
  // AD-07
  title: '실행 기록',
  subtitle: '수집과 산정을 돌린 결과와 로그를 봅니다.',
  period: '기간',
  periods: [
    { value: '7', label: '최근 7일' },
    { value: '30', label: '최근 30일' },
    { value: '90', label: '최근 90일' },
  ],
  status: '상태',
  statuses: ['전체', '성공', '실패', '경고', '실행 중', '건너뜀'],
  head: ['실행 이름', '종류', '상태', '시작 시각', '소요 시간'],
  minutes: (n) => (n == null ? '-' : `${n}분`),
  empty: '이 기간에 실행한 기록이 없습니다.',
  caption: '실행 기록',
  failedArea: '실행 기록',
  logTitle: '로그',
  cause: (c) => `실패 원인: ${c}`,
  rerun: '처음부터 다시 실행하기',
  rerunHelp: '실패한 단계만이 아니라 처음부터 다시 계산합니다.',
  // 서버 업무 오류 문구 (정의서 12 오류 케이스 추가안, 제안)
  noLogs: '로그를 불러오지 못했습니다.',
  cannotRerun: '이 실행은 화면에서 다시 실행할 수 없습니다. 다시 실행이 필요하면 RADAR 개발팀에 요청해 주세요.',
  rerunErrors: {
    notFailed: '실패한 실행만 다시 실행할 수 있습니다. 실행 기록을 새로 불러왔습니다.',
    notSupported: '이 실행은 화면에서 다시 실행할 수 없습니다. 다시 실행이 필요하면 RADAR 개발팀에 요청해 주세요.',
    alreadyRunning: '같은 실행이 이미 돌고 있습니다. 끝난 뒤 실행 기록을 확인해 주세요.',
  },
};

export const SCHEDULE = {
  // AD-08
  title: '실행 일정',
  subtitle: '정기 수집과 산정 일정을 볼 수 있습니다.',
  // M-9: 지금은 일정만 보이고 실행은 사람이 한다. 자동 실행은 확장이다.
  notice: '자동 실행은 확장 기능입니다. 지금은 일정만 보이고, 실행은 회차 목록에서 직접 시작합니다.',
  head: ['작업', '주기', '다음 예정일', '마지막 실행'],
  caption: '실행 일정',
  failedArea: '실행 일정',
};
