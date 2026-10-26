import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../app/providers/AuthProvider.jsx';
import { ROLE } from '../../shared/constants.js';
import { AdminProvider } from '../AdminProvider.jsx';
import {settingsBackendEnabled,i07BackendEnabled} from '../../api/backend.js';

/** 어드민은 RADAR 운영자만 들어온다. 다른 역할은 자기 첫 화면으로 돌려보낸다 (CM-01 U-04). */
export default function RequireOperator() {
  const { user,checking,sessionError,signOut } = useAuth();
  const {pathname}=useLocation();
  if(checking) return <p role="status">로그인을 확인하고 있습니다.</p>;
  if(sessionError) return <div role="alert">{sessionError}<button onClick={signOut}>다시 로그인</button></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== ROLE.OPERATOR || user.readOnly) return <Navigate to={i07BackendEnabled?'/reference/approvals':'/candidates'} replace />;
  if(settingsBackendEnabled){
    if(!/^\/admin\/standards\/criteria(?:\/[^/]+)?\/?$/.test(pathname)) return <Navigate to="/admin/standards/criteria" replace/>;
    return <Outlet/>;
  }
  return (
    <AdminProvider>
      <Outlet />
    </AdminProvider>
  );
}
