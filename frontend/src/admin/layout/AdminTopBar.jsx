import { useState } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../app/providers/AuthProvider.jsx';
import { SelectInput } from '../components/Field.jsx';
import Button from '../components/Button.jsx';
import { useAdmin } from '../AdminProvider.jsx';
import { ADMIN_COPY } from '../copy.js';
import AdminNotifications from './AdminNotifications.jsx';
import ViewAsDialog from './ViewAsDialog.jsx';
import styles from './AdminTopBar.module.css';

/** AD-00 상단 바 (56px): 서비스 이름, 1단계 메뉴, 관리 지자체, 회차, 알림, 사용자 화면 보기, 소속 (디자인 시스템 6-1) */
export default function AdminTopBar() {
  const { user, signOut } = useAuth();
  const { runs, run, setRunId } = useAdmin();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [viewAsOpen, setViewAsOpen] = useState(false);

  const onLogout = async () => {
    await signOut();
    navigate('/login', { replace: true });
  };

  return (
    <header className={styles.bar}>
      <Link to="/admin" className={styles.brand}>
        {ADMIN_COPY.serviceName}
      </Link>
      <nav aria-label={ADMIN_COPY.mainMenuLabel} className={styles.nav}>
        {ADMIN_COPY.menu.map((m) => {
          const to = m.to || m.items[0].to;
          const active = m.to ? pathname === m.to : m.items.some((i) => pathname.startsWith(i.to));
          return (
            <NavLink key={m.key} to={to} end={!!m.to} className={`${styles.tab} ${active ? styles.active : ''}`} aria-current={active ? 'page' : undefined}>
              {m.label}
            </NavLink>
          );
        })}
      </nav>

      <div className={styles.tools}>
        <span className={styles.muni}>
          <span className="sr-only">{ADMIN_COPY.municipalityLabel}</span>
          {ADMIN_COPY.municipality}
        </span>
        <SelectInput
          inline
          label={ADMIN_COPY.runLabel}
          value={run.id}
          onChange={setRunId}
          options={runs.map((r) => ({ value: r.id, label: ADMIN_COPY.runOption(r.name, r.status) }))}
        />
        <AdminNotifications />
        <Button variant="soft" compact onClick={() => setViewAsOpen(true)}>
          {ADMIN_COPY.viewAs.button}
        </Button>
        <div className={styles.account}>
          <span className={styles.org}>{user.org}</span>
          <button type="button" className={styles.logout} onClick={onLogout}>
            {ADMIN_COPY.logout}
          </button>
        </div>
      </div>
      {viewAsOpen ? <ViewAsDialog onClose={() => setViewAsOpen(false)} /> : null}
    </header>
  );
}
