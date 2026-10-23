// 산정 묶음 문구 (10_3_화면명세_어드민 AD-06~AD-08). 기능정의서 문구가 바뀌면 이 파일만 고친다.

export const RUNS = {
  // AD-06
  title: '회차 목록',
  subtitle: '회차를 만들고 산정을 실행한 뒤 검토 중으로 엽니다.',
  create: '회차 만들기',
  head: ['회차', '종류', '상태', '산정 기준 버전', '만든 날', '검토 시작일'],
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
  suggest: (year, kind) => (kind === '연간' ? `${year} 연간` : `${year} 상반기 참고`),

  // 2-1 회차 열기 확인 창
  openTitle: (name) => `${name} 회차를 검토 중으로 열까요?`,
  openClose: '회차 열기 창 닫기',
  openSub: '열면 시 도로과와 3개 구 도로관리팀 화면에 보이고 알림이 갑니다.',
  missingTitle: '빠진 자료',
  unratedTitle: '미평가 분야',
  refNote: '반기 참고 회차는 참고 상태로 열리고 결정을 받지 않습니다.',
  goMissing: '빠진 자료 올리러 가기',
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
  head: ['실행 이름', '종류', '상태', '시작', '걸린 시간'],
  minutes: (n) => (n == null ? '-' : `${n}분`),
  empty: '이 기간에 실행한 기록이 없습니다.',
  caption: '실행 기록',
  failedArea: '실행 기록',
  logTitle: '로그',
  cause: (c) => `실패 원인: ${c}`,
  rerun: '처음부터 다시 실행하기',
  rerunHelp: '실패한 단계만이 아니라 처음부터 다시 계산합니다.',
};

export const SCHEDULE = {
  // AD-08
  title: '실행 일정',
  subtitle: '정기 수집과 산정 일정을 봅니다. 자동 실행은 아직 지원하지 않아 일정만 보여 줍니다.',
  head: ['작업', '주기', '다음 예정일', '마지막 실행'],
  caption: '실행 일정',
  failedArea: '실행 일정',
};
