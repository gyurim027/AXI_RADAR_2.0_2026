// 가짜 회차. 상태: 산정 중 / 검토 중 / 확정 / 참고 (0_안내 용어, US-00 1-1)
import { RUN_STATUS } from '../shared/constants.js';

export const RUNS = [
  {
    id: 'r2027',
    name: '2027 연간',
    kind: 'annual',
    status: RUN_STATUS.REVIEW,
    openedAt: '2026-11-01',
    dataRange: '2022.12 ~ 2026.06',
    version: 'v1.2',
    unratedFields: ['연결성'],
    hasComplaints: true,
    conditionCount: 2,
    dataCount: 31,
  },
  {
    id: 'r2026h2',
    name: '2026 하반기 참고',
    kind: 'ref',
    status: RUN_STATUS.REF,
    openedAt: '2026-07-15',
    dataRange: '2022.12 ~ 2026.06',
    version: 'v1.2',
    unratedFields: ['연결성'],
    hasComplaints: true,
    conditionCount: 2,
    dataCount: 31,
  },
  {
    id: 'r2026',
    name: '2026 연간',
    kind: 'annual',
    status: RUN_STATUS.FINAL,
    openedAt: '2025-12-01',
    dataRange: '2022.12 ~ 2025.06',
    version: 'v1.1',
    unratedFields: ['연결성'],
    hasComplaints: false, // 첫 해: 민원 자료 없음 (US-03 1-2 빈 화면 문구, US-11 메뉴 숨김)
    conditionCount: 1,
    dataCount: 29,
  },
  {
    // 산정 중인 회차는 사용자 화면에 보이지 않는다 (US-00 1-1)
    id: 'r2028',
    name: '2028 연간',
    kind: 'annual',
    status: RUN_STATUS.DRAFT,
    openedAt: null,
    dataRange: '2023.12 ~ 2027.06',
    version: 'v1.3',
    unratedFields: ['연결성'],
    hasComplaints: true,
    conditionCount: 2,
    dataCount: 31,
  },
];
