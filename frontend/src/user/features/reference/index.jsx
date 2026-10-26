import RequireRole from '../../../shared/auth/RequireRole.jsx';
import { ROLE } from '../../../shared/constants.js';
import ApprovalsPage from './pages/ApprovalsPage.jsx';
import DataListPage from './pages/DataListPage.jsx';
import RegulationsPage from './pages/RegulationsPage.jsx';
import ActionsPage from './pages/ActionsPage.jsx';

// 승인 대기(시 도로과만)와 참고 자료 3개. 분류 검수는 어드민에서만 한다(확장으로 미룸).
const only = (roles, el) => <RequireRole roles={roles}>{el}</RequireRole>;

export const referenceRoutes = [
  { path: 'reference/approvals', element: only([ROLE.CITY], <ApprovalsPage />), handle: { title: '승인 대기', reading: true } },
  { path: 'reference/data', element: <DataListPage />, handle: { title: '데이터 목록', reading: true } },
  { path: 'reference/regulations', element: <RegulationsPage />, handle: { title: '법령 및 규정', reading: true } },
  { path: 'reference/actions', element: <ActionsPage />, handle: { title: '조치 제안', reading: true } },
];
