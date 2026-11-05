// 소개 화면 문구. 서비스 소개는 문장으로, 나머지는 짧은 목록으로 쓴다.
// 문제·해결·기대효과의 사실은 PRD v0.3(2026.10.19) 기준이다.
export const WELCOME = {
  eyebrow: '성남시 보행 안전 정기 점검',
  title: 'RADAR 보도 점검 우선순위',
  lead: '성남시 3개 구에서 먼저 점검할 곳을 근거와 함께 제안하는 서비스입니다.',
  startDistrict: '점검 후보 보기',
  startOperator: '어드민 열기',
  menuLabel: '소개',

  introTitle: '서비스 소개',
  cards: [
    {
      key: 'problem',
      title: '문제',
      body: '성남시 보행자길 실태조사는 11개 구간(5.1km)만 표본으로 조사해 도로의 약 0.8%를 확인했습니다. 사고, 시설, 민원 자료는 여러 곳에 흩어져 있고 구마다 쏠려 있어 같은 기준으로 비교하기 어렵습니다.',
    },
    {
      key: 'solution',
      title: '해결',
      body: '3개 구 전체를 구역(격자)으로 나누어 해마다 점검 우선순위를 계산합니다. 후보마다 근거, 자료 기준일, 빠진 자료를 확인할 수 있고, 확정한 대상은 담당 부서별 점검 요청서로 받을 수 있습니다. 최종 결정은 도로관리팀이 합니다.',
    },
    {
      key: 'effect',
      title: '기대효과',
      body: '성남 전역을 해마다 빠짐없이 검토하고, 선정 이유와 근거를 기록으로 남깁니다. 담당 부서까지 요청이 이어져 업무 시간 절감과 보행 환경 개선을 기대할 수 있습니다.',
    },
  ],
  pocNote: 'RADAR는 PoC용 MVP입니다. 업무 시간 절감과 보행 환경 개선 효과는 실제 업무에 적용하면서 확인해 갑니다.',

  flowTitle: '이렇게 사용합니다',
  flow: [
    { key: 'view', label: '점검 후보 보기', text: '지도와 목록에서 후보 확인', help: null },
    { key: 'basis', label: '근거 확인', text: '점검 필요도, 자료 기준일, 빠진 자료 확인', help: '점검 필요도는 100점 만점이며, 점수가 높을수록 먼저 점검할 필요가 있습니다.' },
    { key: 'decide', label: '결정', text: '우선 점검 대상, 제외, 보류 중 선택하고 사유 기록', help: null },
    { key: 'confirm', label: '확정', text: '구 단위로 우선 점검 대상 확정', help: '3개 구가 모두 확정하면 그해 회차가 확정됩니다.' },
    { key: 'request', label: '점검 요청서', text: '담당 부서별로 받기', help: null },
  ],
  roles: [
    { key: 'district', label: '구 도로관리팀', text: '자기 구의 후보 확인, 결정, 확정' },
    { key: 'city', label: '시 도로과', text: '3개 구 현황 확인, 공통 기준 승인' },
    { key: 'operator', label: 'RADAR 운영자', text: '자료, 기준, 회차, 계정 관리' },
  ],
  terms: [
    { key: 'cell', label: '구역(격자)', help: '성남시를 일정한 크기로 나눈 단위입니다. 점수는 구역마다 계산합니다.' },
    { key: 'unrated', label: '미평가', help: '자료가 없어 평가하지 못한 분야입니다. 0점으로 처리하지 않았습니다.' },
    { key: 'run', label: '회차', help: '연도별로 계산한 점검 순위 한 묶음입니다.' },
  ],
  termsTitle: '용어',

  historyTitle: '만든 과정',
  history: [
    { key: 'plan', step: '1단계', period: '약 2주', title: '기획과 데이터 수집', people: '기획 - 배규림 / 우선순위 계산 엔진 - 김진규 / 데이터 수집 - 김은경, 정세은, 김대환, 허진이' },
    { key: 'dev', step: '2단계', period: '약 2주', title: '개발', people: '전원' },
  ],
};
