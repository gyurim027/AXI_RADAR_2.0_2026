// 04_권한표를 사용자 화면 기준으로 옮긴 표. 화면마다 역할을 따로 판단하지 않고 여기서만 본다.
// MVP에서 RADAR에 로그인하는 역할은 도로관리팀(3개 구), 시 도로과, RADAR 운영자 셋이다.
import { ROLE, RUN_STATUS } from '../constants.js';

/** 메뉴 구성 (10_1_메뉴구조, 10_2 US-00 0-1). 보이지 않는 메뉴는 아예 넣지 않는다. */
export function buildMenu(user, run) {
  const district = user.role === ROLE.DISTRICT;
  const city = user.role === ROLE.CITY;
  return [
    { key: 'candidates', label: '점검 후보', to: '/candidates' },
    {
      key: 'reports',
      label: '보고서',
      items: [
        district && { to: '/reports/annual', label: '관할 부서별 연간 보고서' },
        { to: '/reports/basis', label: '구별 우선 점검 근거표' },
        { to: '/reports/conditions', label: '산정 조건 기록서' },
        city && { to: '/reports/protection-zone', label: '보호구역 안팎 비교표' },
        { to: '/reports/half-year', label: '반기 변경 요약' },
      ].filter(Boolean),
    },
    {
      key: 'reference',
      label: '기준정보',
      items: [
        city && { to: '/reference/approvals', label: '승인 대기' },
        // 민원 자료가 없는 회차에는 분류 검수 메뉴를 숨긴다 (US-11, 조건부)
        district && run?.hasComplaints && { to: '/reference/classification', label: '분류 검수' },
        { to: '/reference/data', label: '데이터 목록' },
        { to: '/reference/regulations', label: '규정 변경' },
        { to: '/reference/actions', label: '조치 제안 표' },
      ].filter(Boolean),
    },
  ];
}

/** 결정·확정 버튼은 '검토 중' 회차의 도로관리팀에게만 보인다. 회색으로 막지 않고 숨긴다 (CM-00 10번). */
export function canDecide(user, run) {
  return user.role === ROLE.DISTRICT && run?.status === RUN_STATUS.REVIEW;
}
