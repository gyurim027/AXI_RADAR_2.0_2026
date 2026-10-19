import { createBrowserRouter, Navigate } from 'react-router-dom';
import RequireUser from './RequireUser.jsx';
import UserLayout from '../user/layout/UserLayout.jsx';
import LoginPage from '../user/features/login/pages/LoginPage.jsx';
import AdminPlaceholder from '../admin/AdminPlaceholder.jsx';
import { candidateRoutes } from '../user/features/candidates/index.jsx';
import { reportRoutes } from '../user/features/reports/index.jsx';
import { referenceRoutes } from '../user/features/reference/index.jsx';

// handle.fullHeight: 화면 전체 높이를 쓰는 목록+지도 화면 (디자인 시스템 9-1)
export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/admin/*', element: <AdminPlaceholder /> },
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
          { path: '*', element: <Navigate to="/candidates" replace /> },
        ],
      },
    ],
  },
]);
