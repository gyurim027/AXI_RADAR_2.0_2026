import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../app/providers/AuthProvider.jsx';
import { ROLE } from '../../shared/constants.js';
import { AdminProvider } from '../AdminProvider.jsx';
import {isOpenInServerMode} from '../serverRoutes.js';
import {settingsBackendEnabled,opsBackendEnabled,i07BackendEnabled,backendHome} from '../../api/backend.js';

/** 어드민은 RADAR 운영자만 들어온다. 다른 역할은 자기 첫 화면으로 돌려보낸다 (CM-01 U-04). */
export default function RequireOperator() {
  const { user,checking,sessionError,signOut } = useAuth();
  const {pathname}=useLocation();
  if(checking) return <p role="status">로그인을 확인하고 있습니다.</p>;
  if(sessionError) return <div role="alert">{sessionError}<button onClick={signOut}>다시 로그인</button></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== ROLE.OPERATOR || user.readOnly) return <Navigate to={i07BackendEnabled?'/reference/approvals':'/candidates'} replace />;
  if(settingsBackendEnabled||opsBackendEnabled){
    // 서버에 연결한 화면만 연다. 연결하지 않은 화면은 목업 로그인이 없어 열 수 없다.
    if(!isOpenInServerMode(pathname)) return <Navigate to={backendHome(user.role)} replace/>;
    return <Outlet/>;
  }
  return (
    <AdminProvider>
      <Outlet />
    </AdminProvider>
  );
}
