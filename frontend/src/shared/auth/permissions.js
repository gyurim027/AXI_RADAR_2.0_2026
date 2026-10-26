// 04_권한표를 사용자 화면 기준으로 옮긴 표. 화면마다 역할을 따로 판단하지 않고 여기서만 본다.
// MVP에서 RADAR에 로그인하는 역할은 도로관리팀(3개 구), 시 도로과, RADAR 운영자 셋이다.
import { ROLE, RUN_STATUS } from '../constants.js';

/**
 * 메뉴 구성 (10_1_메뉴구조, 10_2 US-00 0-1). 보이지 않는 메뉴는 아예 넣지 않는다.
 * 1Depth는 점검 후보 · 보고서 · 승인 대기(시 도로과만) · 참고 자료다.
 * items가 있는 메뉴는 화면 아래 하위 탭 줄로 보이고, 탭 이름은 6자 안팎의 짧은 이름이다 (UX 고도화 3-1).
 * 화면 제목과 파일 이름의 전체 이름은 각 화면의 copy.js에 있다.
 */
export function buildMenu(user) {
  const district = user.role === ROLE.DISTRICT;
  const city = user.role === ROLE.CITY;
  return [
    { key: 'candidates', label: '점검 후보', to: '/candidates' },
    {
      key: 'reports',
      label: '보고서',
      items: [
        district && { to: '/reports/annual', label: '점검 요청서' },
        { to: '/reports/basis', label: '구별 근거표' },
        { to: '/reports/conditions', label: '점수 근거' },
        city && { to: '/reports/protection-zone', label: '보호구역 비교' },
        { to: '/reports/half-year', label: '반기 순위 변경' },
      ].filter(Boolean),
    },
    city && { key: 'approvals', label: '승인 대기', to: '/reference/approvals', badge: 'approvals' },
    {
      key: 'reference',
      label: '참고 자료',
      items: [
        { to: '/reference/data', label: '데이터 목록' },
        { to: '/reference/regulations', label: '법령 및 규정' },
        { to: '/reference/actions', label: '조치 제안' },
      ],
    },
  ].filter(Boolean);
}

/** 지금 주소가 속한 하위 탭 묶음. 하위 탭이 없는 메뉴면 null이다. */
export function activeGroup(menu, pathname) {
  return menu.find((m) => m.items && m.items.some((i) => pathname.startsWith(i.to))) || null;
}

/** 결정·확정 버튼은 '검토 중' 회차의 도로관리팀에게만 보인다. 회색으로 막지 않고 숨긴다 (CM-00 10번). */
export function canDecide(user, run) {
  return user.role === ROLE.DISTRICT && run?.status === RUN_STATUS.REVIEW;
}
