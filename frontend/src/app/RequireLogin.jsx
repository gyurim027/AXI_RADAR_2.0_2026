import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from './providers/AuthProvider.jsx';

/** 로그인한 모든 역할이 들어온다. 역할별 화면 틀(사용자·어드민)에 갇히지 않는 화면에 쓴다. */
export default function RequireLogin() {
  const { user, checking, sessionError, signOut } = useAuth();
  const location = useLocation();
  if (checking) return <p role="status">로그인을 확인하고 있습니다.</p>;
  if (sessionError) return <div role="alert">{sessionError}<button onClick={signOut}>다시 로그인</button></div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}
