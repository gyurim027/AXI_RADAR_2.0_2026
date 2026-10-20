import DashboardPage from './features/dashboard/DashboardPage.jsx';

// handle.title: 브라우저 탭 제목 / handle.wide: 본문 폭 제한 없이 쓰는 화면
export const adminRoutes = [{ index: true, element: <DashboardPage />, handle: { title: '대시보드' } }];
