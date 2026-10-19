import RequireRole from '../../../shared/auth/RequireRole.jsx';
import { ROLE } from '../../../shared/constants.js';
import AnnualReportPage from './pages/AnnualReportPage.jsx';
import BasisPage from './pages/BasisPage.jsx';
import ConditionRecordPage from './pages/ConditionRecordPage.jsx';
import ProtectionZonePage from './pages/ProtectionZonePage.jsx';
import HalfYearPage from './pages/HalfYearPage.jsx';

// 보고서 5개. 역할에 없는 화면은 주소로 들어와도 열리지 않는다.
const only = (roles, el) => <RequireRole roles={roles}>{el}</RequireRole>;
const page = (title) => ({ title });

export const reportRoutes = [
  { path: 'reports/annual', element: only([ROLE.DISTRICT], <AnnualReportPage />), handle: page('관할 부서별 연간 보고서') },
  { path: 'reports/basis', element: <BasisPage />, handle: page('구별 우선 점검 근거표') },
  { path: 'reports/conditions', element: <ConditionRecordPage />, handle: page('산정 조건 기록서') },
  { path: 'reports/protection-zone', element: only([ROLE.CITY], <ProtectionZonePage />), handle: page('보호구역 안팎 비교표') },
  { path: 'reports/half-year', element: <HalfYearPage />, handle: page('반기 변경 요약') },
];
