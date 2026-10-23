import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../../app/providers/AuthProvider.jsx';
import { ROLE } from '../../shared/constants.js';
import { AdminProvider } from '../AdminProvider.jsx';

/** 어드민은 RADAR 운영자만 들어온다. 다른 역할은 자기 첫 화면으로 돌려보낸다 (CM-01 U-04). */
export default function RequireOperator() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== ROLE.OPERATOR || user.readOnly) return <Navigate to="/candidates" replace />;
  return (
    <AdminProvider>
      <Outlet />
    </AdminProvider>
  );
}
