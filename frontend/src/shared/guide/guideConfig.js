// 화면 첫 진입 안내(코치마크). 기능정의서 v0.5.5의 사용자 플로우(U-nn)·메뉴구조(US·AD)·화면 설명 기준으로
// 핵심 시나리오의 핵심 기능만 담는다. target은 안내할 요소의 CSS 선택자이고, 요소가 없으면 그 단계는 건너뛴다.
// roles를 적은 단계는 그 역할에게만 보인다. scene은 카드 위 미니 애니메이션 이름이다.
const D = ['district'];
const C = ['city'];

export const GUIDE_COPY = {
  skip: '건너뛰기',
  next: '다음',
  done: '끝',
  helpMenuLabel: '도움말',
  replayScreen: '이 화면 안내 다시 보기',
  openWelcome: '서비스 소개 보기',
  pagesLabel: '안내 단계',
  nextTitle: (label) => `다음은 ${label}`,
};

// 역할별 핵심 경로(화면 키 순서). 안내의 마지막 카드가 다음 화면으로 이어 준다.
// 서버 연결 모드에서 열리지 않는 화면은 경로에서 건너뛴다.
export const FLOWS = {
  operator: ['admin-dashboard', 'admin-criteria', 'admin-runs'],
  district: ['candidates', 'annual'],
  city: ['candidates', 'approvals', 'conditions'], // 첫 메뉴(점검 후보)에서 시작해 승인 대기, 점수 근거로 이어진다
};

export const SCREENS = [
  {
    key: 'candidates',
    path: '/candidates',
    menuLabel: '점검 후보',
    entry: ['`점검 후보` 메뉴에서 엽니다.', '3개 구 후보를 보기 전용으로 확인합니다.'],
    spotlight: 'header nav a[href="/candidates"]',
    match: /^\/candidates\/?$/,
    steps: [
      { target: '#run-select', scene: 'select', title: '점검 연도 선택', bullets: ['지금 볼 회차를 고릅니다.', '검토 중이 아닌 회차는 위쪽 상태 띠로 알려 줍니다.'] },
      { target: '#gu-select', roles: C, scene: 'select', title: '구 선택', bullets: ['볼 구를 고릅니다.', '3개 구 전체도 볼 수 있습니다.'] },
      { target: '[data-guide="filter"]', scene: 'menu', title: '필터로 좁히기', bullets: ['보행 방해요소, 자료 신뢰도, 보호구역, 민원 쏠림으로 후보를 좁힙니다.'] },
      { target: '[data-guide="compare"]', roles: C, scene: 'button', label: '구별 비교', title: '구별 비교 보기', bullets: ['구마다 기록이 쏠렸는지 확인합니다.'] },
      { target: 'section[aria-label="점검 후보 목록"]', scene: 'row', title: '후보 고르기', bullets: ['후보를 누르면 지도에 요약이 뜹니다.', '요약에서 상세를 열면 순위 근거, 관련 조문, 담당 부서, 작년 결정을 볼 수 있습니다.'] },
      { target: 'section[aria-label="점검 후보 목록"]', roles: D, scene: 'menu', title: '결정 기록', bullets: ['우선 점검 대상, 제외, 보류 중 하나를 고릅니다.', '제외와 보류는 사유를 함께 적습니다.'] },
      { target: '[data-guide="map"]', scene: 'map', title: '지도 보기', bullets: ['점검 필요도가 높은 구역일수록 진하게 보입니다.', 'Ctrl을 누른 채 휠을 돌리면 지도가 확대됩니다.'] },
      { target: '[data-guide="confirm"]', roles: D, scene: 'button', label: '확정', title: '우선 점검 대상 확정', bullets: ['자기 구 검토를 마치면 확정합니다.', '3개 구가 모두 확정하면 그해 회차가 확정됩니다.'] },
    ],
  },
  {
    key: 'annual',
    path: '/reports/annual',
    menuLabel: '점검 요청서',
    entry: ['`보고서` 메뉴의 `점검 요청서`에서 엽니다.', '확정한 대상을 관할 부서별 요청서로 확인합니다.'],
    done: { title: '관할 부서에 전달해 주세요', bullets: ['부서별 점검 요청서를 확인하고 관할 부서 담당자에게 전달합니다.', '시 도로과는 3개 구의 확정 현황과 근거를 확인합니다.'] },
    spotlight: 'header nav a[href^="/reports/"]',
    match: /^\/reports\/annual\/?$/,
    steps: [{ target: 'main table', scene: 'row', title: '점검 요청서', bullets: ['관할 부서별로 대상 목록, 근거, 요청안, 조치 제안을 확인합니다.'] }],
  },
  {
    key: 'conditions',
    path: '/reports/conditions',
    menuLabel: '점수 근거',
    entry: ['`보고서` 메뉴의 `점수 근거`에서 엽니다.', '회차에 쓴 자료와 기준을 한 장으로 봅니다.'],
    done: { title: '구별 확정을 확인해 주세요', bullets: ['점검 후보에서 3개 구의 확정 현황을 확인합니다.', '3개 구가 모두 확정하면 그해 회차가 확정됩니다.'] },
    spotlight: 'header nav a[href^="/reports/"]',
    match: /^\/reports\/conditions\/?$/,
    steps: [{ target: 'main table', scene: 'row', title: '우선순위 점수 근거', bullets: ['회차에 쓴 자료와 기준을 한 장으로 남깁니다.'] }],
  },
  {
    key: 'approvals',
    path: '/reference/approvals',
    menuLabel: '승인 대기',
    entry: ['`승인 대기` 메뉴에서 엽니다.', 'RADAR 운영자의 제안을 승인하거나 반려합니다.'],
    spotlight: 'header nav a[href="/reference/approvals"]',
    match: /^\/reference\/approvals\/?$/,
    steps: [{ target: 'main table', roles: C, scene: 'row', title: '승인 대기', bullets: ['RADAR 운영자의 제안을 승인하거나 반려합니다.', '반려할 때는 사유를 적습니다.'] }],
  },
  {
    key: 'admin-dashboard',
    path: '/admin',
    menuLabel: '대시보드',
    entry: ['위쪽 메뉴에서 대시보드를 엽니다.', '회차 상태와 다음에 할 일을 봅니다.'],
    spotlight: 'header nav a[href="/admin"], nav[aria-label="설정 관리"] a[href="/admin"]',
    match: /^\/admin\/?$/,
    steps: [
      { target: '[data-guide="dash-next"]', scene: 'button', title: '회차 준비 상태', bullets: ['지금 회차의 상태와 다음에 할 일을 봅니다.'] },
      { target: '[data-guide="dash-todo"]', scene: 'row', title: '처리할 일', bullets: ['자료 최신 여부, 최근 실행, 승인 현황, 규정 변경을 한눈에 봅니다.'] },
      { target: '[data-guide="dash-base"]', scene: 'row', title: '산정 기준', bullets: ['지금 쓰는 산정 기준 버전과 승인 대기 버전을 봅니다.'] },
    ],
  },
  {
    key: 'admin-runs',
    path: '/admin/runs/list',
    menuLabel: '회차 목록',
    entry: ['위쪽 메뉴에서 회차 목록을 엽니다.', '산정을 시작하고 검토 중으로 엽니다.'],
    done: { title: '다음은 구 도로관리팀 차례입니다', bullets: ['회차를 열면 구 계정에서 점검 후보를 확인하고 결정을 진행합니다.', '3개 구가 모두 확정하면 그해 회차가 확정됩니다.'] },
    spotlight: 'a[href="/admin/runs/list"]:not(header a)',
    match: /^\/admin\/runs\/list\/?$/,
    steps: [
      { target: '[data-guide="run-create"]', scene: 'button', label: '만들기', title: '회차 만들기', bullets: ['새 회차를 만듭니다.'] },
      { target: 'button[aria-label$="산정 시작하기"]', scene: 'button', label: '산정', title: '산정 시작하기', bullets: ['회차의 점수와 순위를 계산합니다.'] },
      { target: 'button[aria-label$="검토 중으로 열기"]', scene: 'button', label: '열기', title: '검토 중으로 열기', bullets: ['열기 전에 빠진 자료와 미평가 분야를 확인합니다.', '열면 구 도로관리팀이 결정을 시작합니다.'] },
    ],
  },
  {
    key: 'admin-criteria',
    path: '/admin/standards/criteria',
    menuLabel: '산정 기준',
    entry: ['위쪽 메뉴에서 산정 기준을 엽니다.', '가중치와 기준값을 고쳐 승인을 요청합니다.'],
    spotlight: 'header nav a[href^="/admin/runs/"], nav[aria-label="설정 관리"] a[href="/admin/standards/criteria"]',
    match: /^\/admin\/standards\/criteria\/?$/,
    steps: [
      { target: 'main table', scene: 'row', title: '산정 기준 버전', bullets: ['버전 목록을 보고, 버전을 누르면 상세로 갑니다.'] },
      { target: '[data-guide="criteria-create"]', scene: 'button', label: '만들기', title: '새 버전 만들기', bullets: ['가중치와 기준값을 고쳐 승인을 요청합니다.'] },
    ],
  },
];
