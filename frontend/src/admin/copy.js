// 어드민 공통 문구. 키 앞의 번호는 10_3_화면명세_어드민의 블록 번호다. 기능정의서 문구가 바뀌면 이 파일만 고친다.
export const ADMIN_COPY = {
  serviceName: 'RADAR 보도 점검 우선순위',
  skip: '본문 바로가기',
  mainMenuLabel: '주 메뉴',
  sectionMenuLabel: '화면 메뉴',

  // AD-00 0-1 메뉴 (10_1_메뉴구조의 1Depth)와 아래 화면들
  menu: [
    { key: 'dashboard', label: '대시보드', to: '/admin' },
    {
      key: 'data',
      label: '데이터',
      items: [
        { to: '/admin/data/list', label: '데이터 목록' },
        { to: '/admin/data/upload', label: '업로드' },
        { to: '/admin/data/checks', label: '검사 결과' },
        { to: '/admin/data/classify', label: '분류 검수' },
      ],
    },
    {
      key: 'runs',
      label: '산정',
      items: [
        { to: '/admin/runs/list', label: '회차 목록' },
        { to: '/admin/runs/log', label: '실행 기록' },
        { to: '/admin/runs/schedule', label: '실행 일정' },
      ],
    },
    {
      key: 'standards',
      label: '기준정보',
      items: [
        { to: '/admin/standards/criteria', label: '산정 기준' },
        { to: '/admin/standards/dept', label: '담당 부서 표' },
        { to: '/admin/standards/regulations', label: '규정 변경' },
        { to: '/admin/standards/actions', label: '조치 제안 표' },
        { to: '/admin/standards/approvals', label: '승인 이력' },
      ],
    },
    {
      key: 'settings',
      label: '설정',
      items: [
        { to: '/admin/settings/accounts', label: '계정' },
        { to: '/admin/settings/access', label: '접속 기록' },
        { to: '/admin/settings/alerts', label: '알림 설정' },
      ],
    },
  ],

  // AD-00 1-1 지자체 표시, 0-2 계정, 2-1 회차 선택
  municipality: '성남시',
  municipalityLabel: '관리 지자체',
  logout: '로그아웃',
  runLabel: '회차',
  runOption: (name, status) => `${name} · ${status}`,

  // AD-00 3-1 알림
  notifications: {
    label: (n) => `알림 ${n}개 보기`,
    title: '알림',
    empty: '새 알림이 없습니다.',
    failed: '알림을 불러오지 못했습니다.',
  },

  // AD-00 4-1 사용자 화면 보기
  viewAs: {
    button: '사용자 화면 보기',
    title: '사용자 화면 보기',
    subtitle: '고른 계정이 보는 화면을 보기 전용으로 엽니다.',
    account: '볼 계정',
    open: '보기 전용으로 열기',
    closeLabel: '사용자 화면 보기 창 닫기',
    band: '%볼 계정% 화면을 보기 전용으로 보는 중입니다.',
    back: '어드민으로 돌아가기',
  },

  // 저장·요청이 실패했을 때 (공통 규칙 12번 말투)
  actionFailed: '처리하지 못했습니다. 잠시 뒤 다시 해 주세요. 계속 안 되면 개발 담당에게 알려 주세요.',

  noValue: '-',
};
