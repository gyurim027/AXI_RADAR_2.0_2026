import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom';
import RequireUser from './RequireUser.jsx';
import WelcomeModal from '../user/features/welcome/WelcomeModal.jsx';
import ScreenGuide from '../shared/guide/ScreenGuide.jsx';
import UserLayout from '../user/layout/UserLayout.jsx';
import LoginPage from '../user/features/login/pages/LoginPage.jsx';
import AdminLayout from '../admin/layout/AdminLayout.jsx';
import RequireOperator from '../admin/layout/RequireOperator.jsx';
import { adminRoutes } from '../admin/routes.jsx';
import { candidateRoutes } from '../user/features/candidates/index.jsx';
import { reportRoutes } from '../user/features/reports/index.jsx';
import NoticePage from '../user/components/NoticePage.jsx';
import { referenceRoutes } from '../user/features/reference/index.jsx';

// 모든 화면 위에 소개 모달(로그인 직후, 메뉴의 `소개`)을 한 곳에서 띄운다
function RootShell() {
  return (
    <>
      <Outlet />
      <WelcomeModal />
      <ScreenGuide />
    </>
  );
}

// handle.fullHeight: 화면 전체 높이를 쓰는 목록+지도 화면 (디자인 시스템 9-1)
const routes = [
  { path: '/login', element: <LoginPage /> },
  {
    path: '/admin',
    element: <RequireOperator />,
    children: [
      {
        element: <AdminLayout />,
        children: [...adminRoutes, { path: '*', element: <NoticePage kind="notFound" home="/admin" /> }],
      },
    ],
  },
  {
    element: <RequireUser />,
    children: [
      {
        element: <UserLayout />,
        children: [
          { index: true, element: <Navigate to="/candidates" replace /> },
          ...candidateRoutes,
          ...reportRoutes,
          ...referenceRoutes,
          { path: '*', element: <NoticePage kind="notFound" /> },
        ],
      },
    ],
  },
];

export const router = createBrowserRouter([{ element: <RootShell />, children: routes }]);
