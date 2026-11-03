import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { backendAuthEnabled, priorityBackendEnabled } from '../api/backend.js';
import { ROLE } from '../shared/constants.js';
import { useAuth } from './providers/AuthProvider.jsx';
import { RunProvider } from './providers/RunProvider.jsx';

/** 로그인한 도로관리팀·시 도로과만 사용자 화면에 들어온다. 운영자는 어드민으로 보낸다 (CM-01, U-04). */
export default function RequireUser() {
  const { user, checking, sessionError, signOut } = useAuth();
  const location = useLocation();
  if (checking) return <p role="status">로그인을 확인하고 있습니다.</p>;
  if (sessionError) return <div role="alert">{sessionError}<button onClick={signOut}>다시 로그인</button></div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (user.role === ROLE.OPERATOR) return <Navigate to="/admin" replace />;
  if (backendAuthEnabled && !priorityBackendEnabled) return <Outlet />; // 서버 연결 모드에서 회차가 연결되지 않으면 가짜 회차를 만들지 않는다
  return (
    <RunProvider>
      <Outlet />
    </RunProvider>
  );
}
