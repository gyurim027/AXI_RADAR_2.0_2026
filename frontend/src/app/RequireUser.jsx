import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { ROLE } from '../shared/constants.js';
import { useAuth } from './providers/AuthProvider.jsx';
import { RunProvider } from './providers/RunProvider.jsx';

/** 로그인한 도로관리팀·시 도로과만 사용자 화면에 들어온다. 운영자는 어드민으로 보낸다 (CM-01, U-04). */
export default function RequireUser() {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (user.role === ROLE.OPERATOR) return <Navigate to="/admin" replace />;
  return (
    <RunProvider>
      <Outlet />
    </RunProvider>
  );
}
