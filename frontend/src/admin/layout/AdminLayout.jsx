import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useMatches } from 'react-router-dom';
import { useAdmin } from '../AdminProvider.jsx';
import { Banner } from '../components/Panel.jsx';
import { onActionError } from '../utils/actionError.js';
import { ADMIN_COPY } from '../copy.js';
import AdminTopBar from './AdminTopBar.jsx';
import SectionNav from './SectionNav.jsx';
import styles from './AdminLayout.module.css';
import topStyles from './AdminTopBar.module.css';
import {settingsBackendEnabled,opsBackendEnabled,backendHome} from '../../api/backend.js';
import {useAuth} from '../../app/providers/AuthProvider.jsx';

/** AD-00 공통 상단 + 본문. 위 두 줄(상단 바, 보조 탐색)은 스크롤해도 맨 위에 고정한다 (디자인 시스템 6-1). */
export default function AdminLayout() {
  return settingsBackendEnabled||opsBackendEnabled?<SettingsLayout/>:<RunAdminLayout/>;
}

function SettingsLayout(){
  const {user,signOut}=useAuth();
  useEffect(()=>{document.title='RADAR 어드민';},[]);
  return <div className={styles.shell}>
    <a href="#admin-main" className={styles.skip}>본문 바로가기</a>
    <div className={styles.fixed}><header className={topStyles.bar}>
      <Link className={topStyles.brand} to={backendHome('operator')}>{ADMIN_COPY.serviceName}</Link>
      <nav className={topStyles.nav} aria-label="설정 관리">
        {settingsBackendEnabled?<NavLink className={topStyles.tab} to="/admin/standards/criteria">산정 기준</NavLink>:null}
        {opsBackendEnabled?[['/admin/settings/accounts','계정'],['/admin/settings/access','접속 기록'],['/admin/settings/alerts','알림 설정']].map(([to,label])=><NavLink key={to} className={topStyles.tab} to={to}>{label}</NavLink>):null}
      </nav>
      <div className={topStyles.tools}><span>{user.org}</span><button className={topStyles.logout} onClick={signOut}>로그아웃</button></div>
    </header></div>
    <main id="admin-main" className={styles.main} tabIndex={-1}><div className={styles.content}><Outlet/></div></main>
  </div>;
}

function RunAdminLayout() {
  const { run } = useAdmin();
  const matches = useMatches();
  const pageTitle = [...matches].reverse().find((m) => m.handle?.title)?.handle.title;
  const wide = matches.some((m) => m.handle?.wide);
  const { pathname } = useLocation();
  const [failedAt, setFailedAt] = useState(null);
  const actionFailed = failedAt === pathname;
  useEffect(() => onActionError(() => setFailedAt(window.location.pathname)), []);

  useEffect(() => {
    document.title = pageTitle ? `${pageTitle} · ${ADMIN_COPY.serviceName}` : ADMIN_COPY.serviceName;
  }, [pageTitle]);

  return (
    <div className={styles.shell}>
      <a href="#admin-main" className={styles.skip}>
        {ADMIN_COPY.skip}
      </a>
      <div className={styles.fixed}>
        <AdminTopBar />
        <SectionNav />
      </div>
      <main id="admin-main" className={styles.main} tabIndex={-1}>
        <div className={`${styles.content} ${wide ? styles.wide : ''}`}>
          {/* 회차를 바꾸면 지금 메뉴를 그 회차로 다시 연다 (AD-00 2-1) */}
          {actionFailed ? (
            <div style={{ marginBottom: 16 }}>
              <Banner tone="danger">{ADMIN_COPY.actionFailed}</Banner>
            </div>
          ) : null}
          <Outlet key={run.id} />
        </div>
      </main>
    </div>
  );
}
