// 설정 묶음 문구 (10_3_화면명세_어드민 AD-15~AD-17). 기능정의서 문구가 바뀌면 이 파일만 고친다.

export const ACCOUNTS = {
  // AD-15
  title: '계정',
  subtitle: '계정을 만들고 역할과 소속을 부여합니다.',
  create: '계정 만들기',
  head: ['이름', '아이디', '역할', '소속 구', '소속 팀', '상태', '최근 접속일'],
  caption: '계정 목록',
  stop: '계정 사용 멈추기',
  resume: '계정 다시 쓰기',
  statusOn: '사용 중',
  statusOff: '멈춤',
  failedArea: '계정 목록',
  actionFailed: '계정 상태를 바꾸지 못했습니다.',

  dialogTitle: '계정 만들기',
  dialogClose: '계정 만들기 창 닫기',
  role: '역할',
  gu: '소속 구',
  team: '소속 팀',
  teamPlaceholder: '예: 보도관리팀',
  name: '이름',
  loginId: '아이디',
  errorGu: '구 도로관리팀은 소속 구를 골라야 합니다.',
  // 명세에 없는 오류 문구: 같은 아이디가 이미 있을 때
  errorDuplicate: '이미 있는 아이디입니다. 다른 아이디를 적어 주세요.',
  done: '계정을 만들었습니다. 첫 로그인 때 비밀번호를 바꾸도록 안내해 주세요.',

  // 서버가 임시 비밀번호를 한 번만 준다 (docs/api/admin_accounts.md). 제안 문구.
  tempTitle: '임시 비밀번호',
  tempNote: (id) => `${id} 계정의 임시 비밀번호입니다. 지금 한 번만 보입니다. 창을 닫으면 다시 볼 수 없으니 받는 분께 직접 전해 주세요.`,
  tempClose: '임시 비밀번호 창 닫기',
  tempDone: '닫기',
  logTitle: '권한 변경 기록',
  logRow: (date, name, from, to, by) => `${date} · ${name} · ${from} → ${to} · ${by}`,
};

export const ACCESS = {
  // AD-16
  title: '접속 기록',
  subtitle: '누가 언제 무엇을 보고 처리했는지 점검합니다. 기록은 고치거나 지울 수 없습니다.',
  period: '기간',
  periods: [
    { value: '7', label: '최근 7일' },
    { value: '30', label: '최근 30일' },
    { value: '90', label: '최근 90일' },
  ],
  account: '계정',
  action: '수행 작업',
  head: ['시각', '계정', '접속 IP', '수행 작업', '대상', '사유'],
  caption: '접속 기록',
  empty: '조건에 맞는 기록이 없습니다.',
  failedArea: '접속 기록',
};

export const ALERTS = {
  // AD-17
  title: '알림 설정',
  subtitle: '수집·산정 실패 알림을 받을 메일을 정합니다.',
  label: '실패 알림 받을 메일',
  help: '메일이 가지 않으면 다음 접속 때 화면에 띄웁니다.',
  save: '알림 메일 저장하기',
  error: '메일 주소 형식이 맞지 않습니다. 예: name@example.com',
  done: '알림 메일을 저장했습니다.',
  failedArea: '알림 설정',
};
