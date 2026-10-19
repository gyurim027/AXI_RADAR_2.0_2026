import RequireRole from '../../../shared/auth/RequireRole.jsx';
import { ROLE } from '../../../shared/constants.js';
import ApprovalsPage from './pages/ApprovalsPage.jsx';
import ClassificationPage from './pages/ClassificationPage.jsx';
import DataListPage from './pages/DataListPage.jsx';
import RegulationsPage from './pages/RegulationsPage.jsx';
import ActionsPage from './pages/ActionsPage.jsx';

// 기준정보 5개. 승인 대기는 시 도로과만, 분류 검수는 도로관리팀만 쓴다.
const only = (roles, el) => <RequireRole roles={roles}>{el}</RequireRole>;

export const referenceRoutes = [
  { path: 'reference/approvals', element: only([ROLE.CITY], <ApprovalsPage />), handle: { title: '승인 대기' } },
  { path: 'reference/classification', element: only([ROLE.DISTRICT], <ClassificationPage />), handle: { title: '분류 검수' } },
  { path: 'reference/data', element: <DataListPage />, handle: { title: '데이터 목록' } },
  { path: 'reference/regulations', element: <RegulationsPage />, handle: { title: '규정 변경' } },
  { path: 'reference/actions', element: <ActionsPage />, handle: { title: '조치 제안 표' } },
];
