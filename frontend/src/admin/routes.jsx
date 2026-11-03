import DashboardPage from './features/dashboard/DashboardPage.jsx';
import ChecksPage from './features/data/ChecksPage.jsx';
import ClassifyPage from './features/data/ClassifyPage.jsx';
import DataListPage from './features/data/DataListPage.jsx';
import UploadPage from './features/data/UploadPage.jsx';
import AccessPage from './features/settings/AccessPage.jsx';
import AccountsPage from './features/settings/AccountsPage.jsx';
import AlertsPage from './features/settings/AlertsPage.jsx';
import ActionsPage from './features/standards/ActionsPage.jsx';
import ApprovalsPage from './features/standards/ApprovalsPage.jsx';
import CriteriaDetailPage from './features/standards/CriteriaDetailPage.jsx';
import CriteriaListPage from './features/standards/CriteriaListPage.jsx';
import DeptPage from './features/standards/DeptPage.jsx';
import RegulationsPage from './features/standards/RegulationsPage.jsx';
import LogPage from './features/runs/LogPage.jsx';
import RunListPage from './features/runs/RunListPage.jsx';
import ServerRunListPage from './features/runs/ServerRunListPage.jsx';
import { opsBackendEnabled } from '../api/backend.js';
import SchedulePage from './features/runs/SchedulePage.jsx';

// handle.title: 브라우저 탭 제목
export const adminRoutes = [
  { index: true, element: <DashboardPage />, handle: { title: '대시보드' } },
  { path: 'data/list', element: <DataListPage />, handle: { title: '데이터 목록' } },
  { path: 'data/upload', element: <UploadPage />, handle: { title: '자료 올리기' } },
  { path: 'data/checks', element: <ChecksPage />, handle: { title: '검사 결과' } },
  { path: 'data/classify', element: <ClassifyPage />, handle: { title: '민원 분류 검수' } },
  { path: 'runs/list', element: opsBackendEnabled ? <ServerRunListPage /> : <RunListPage />, handle: { title: '회차 목록' } },
  { path: 'runs/log', element: <LogPage />, handle: { title: '실행 기록' } },
  { path: 'runs/schedule', element: <SchedulePage />, handle: { title: '실행 일정' } },
  { path: 'standards/criteria', element: <CriteriaListPage />, handle: { title: '산정 기준' } },
  { path: 'standards/criteria/:version', element: <CriteriaDetailPage />, handle: { title: '산정 기준 상세' } },
  { path: 'standards/dept', element: <DeptPage />, handle: { title: '담당 부서 표' } },
  { path: 'standards/regulations', element: <RegulationsPage />, handle: { title: '규정 변경' } },
  { path: 'standards/actions', element: <ActionsPage />, handle: { title: '조치 제안 표' } },
  { path: 'standards/approvals', element: <ApprovalsPage />, handle: { title: '승인 이력' } },
  { path: 'settings/accounts', element: <AccountsPage />, handle: { title: '계정' } },
  { path: 'settings/access', element: <AccessPage />, handle: { title: '접속 기록' } },
  { path: 'settings/alerts', element: <AlertsPage />, handle: { title: '알림 설정' } },
];
