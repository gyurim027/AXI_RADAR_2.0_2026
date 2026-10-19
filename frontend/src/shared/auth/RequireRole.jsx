import { Navigate } from 'react-router-dom';
import { useAuth } from '../../app/providers/AuthProvider.jsx';

/** 역할에 없는 화면은 메뉴에도 없고 주소로 들어와도 열리지 않는다 (10_2 '이 역할에는 보이지 않음') */
export default function RequireRole({ roles, children }) {
  const { user } = useAuth();
  if (!user || !roles.includes(user.role)) return <Navigate to="/candidates" replace />;
  return children;
}
