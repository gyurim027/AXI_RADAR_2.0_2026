import { createBrowserRouter, Navigate } from 'react-router-dom';
import RequireUser from './RequireUser.jsx';
import RequireLogin from './RequireLogin.jsx';
import WelcomePage from '../user/features/welcome/pages/WelcomePage.jsx';
import { WELCOME_PATH } from '../user/features/welcome/landing.js';
import UserLayout from '../user/layout/UserLayout.jsx';
import LoginPage from '../user/features/login/pages/LoginPage.jsx';
import AdminLayout from '../admin/layout/AdminLayout.jsx';
import RequireOperator from '../admin/layout/RequireOperator.jsx';
import { adminRoutes } from '../admin/routes.jsx';
import { candidateRoutes } from '../user/features/candidates/index.jsx';
import { reportRoutes } from '../user/features/reports/index.jsx';
import NoticePage from '../user/components/NoticePage.jsx';
import { referenceRoutes } from '../user/features/reference/index.jsx';

// handle.fullHeight: 화면 전체 높이를 쓰는 목록+지도 화면 (디자인 시스템 9-1)
export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  // 로그인 직후 소개 화면: 어느 역할이든 열 수 있어 사용자·어드민 틀 밖에 둔다
  { element: <RequireLogin />, children: [{ path: WELCOME_PATH, element: <WelcomePage /> }] },
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
]);
