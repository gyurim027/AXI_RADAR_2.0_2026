import { NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../../app/providers/AuthProvider.jsx';
import { activeGroup, buildMenu } from '../../shared/auth/permissions.js';
import styles from './SubNav.module.css';

/** 하위 탭 줄 (UX 고도화 M-1). 보고서·참고 자료처럼 아래 화면이 여럿인 메뉴에서만 보인다. */
export default function SubNav() {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const group = activeGroup(buildMenu(user), pathname);
  if (!group) return null;
  return (
    <nav aria-label={`${group.label} 화면`} className={styles.nav}>
      {group.items.map((i) => (
        <NavLink key={i.to} to={i.to} className={({ isActive }) => `${styles.item} ${isActive ? styles.active : ''}`}>
          {i.label}
        </NavLink>
      ))}
    </nav>
  );
}
