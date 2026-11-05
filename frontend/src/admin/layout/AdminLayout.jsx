import AppVersion from '../../shared/components/AppVersion.jsx';
import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useMatches } from 'react-router-dom';
import { useAdmin } from '../AdminProvider.jsx';
import { Banner } from '../components/Panel.jsx';
import { onActionError } from '../utils/actionError.js';
import { ADMIN_COPY } from '../copy.js';
import AdminNotifications from './AdminNotifications.jsx';
import HelpMenu from '../../shared/guide/HelpMenu.jsx';
import { EmptyState } from '../components/States.jsx';
import { isOpenInServerMode } from '../serverRoutes.js';
import AdminTopBar from './AdminTopBar.jsx';
import SectionNav from './SectionNav.jsx';
import styles from './AdminLayout.module.css';
import topStyles from './AdminTopBar.module.css';
import sectionStyles from './SectionNav.module.css';
import {settingsBackendEnabled,opsBackendEnabled,priorityBackendEnabled,backendHome} from '../../api/backend.js';
import {useAuth} from '../../app/providers/AuthProvider.jsx';

/** AD-00 공통 상단 + 본문. 위 두 줄(상단 바, 보조 탐색)은 스크롤해도 맨 위에 고정한다 (디자인 시스템 6-1). */
export default function AdminLayout() {
  return settingsBackendEnabled||opsBackendEnabled?<SettingsLayout/>:<RunAdminLayout/>;
}

function SettingsLayout(){
  const {user,signOut}=useAuth();
  const {pathname}=useLocation();
  const [failed,setFailed]=useState(null);
  useEffect(()=>{document.title='RADAR 어드민';},[]);
  useEffect(()=>onActionError((message)=>setFailed({path:window.location.pathname,message})),[]);
  const banner=failed&&failed.path===pathname?failed.message||ADMIN_COPY.actionFailed:null;
  const on={ops:opsBackendEnabled,settings:settingsBackendEnabled,priority:priorityBackendEnabled};
  const menu=ADMIN_COPY.serverMenu.filter((m)=>on[m.need]);
  return <div className={styles.shell}>
    <a href="#admin-main" className={styles.skip}>본문 바로가기</a>
    <div className={styles.fixed}>
      <header className={topStyles.bar}>
        <Link className={topStyles.brand} to={backendHome('operator')}>{ADMIN_COPY.serviceName}</Link>
        <div className={topStyles.tools}>{opsBackendEnabled?<AdminNotifications/>:null}<HelpMenu/><span className={topStyles.org}>{user.org}</span><button className={topStyles.logout} onClick={signOut}>로그아웃</button></div>
      </header>
      <nav className={sectionStyles.nav} aria-label="설정 관리">
        {menu.map((m)=><NavLink key={m.to} to={m.to} end={m.end} className={({isActive})=>`${sectionStyles.item} ${isActive?sectionStyles.active:''}`}>{m.label}</NavLink>)}
      </nav>
    </div>
    <main id="admin-main" className={styles.main} tabIndex={-1}><div className={styles.content}>{banner?<div style={{marginBottom:16}}><Banner tone="danger">{banner}</Banner></div>:null}{isOpenInServerMode(pathname)?<Outlet/>:<div role="status"><EmptyState text="이 화면은 아직 서버와 연결되지 않았습니다."/></div>}<AppVersion/></div></main>
  </div>;
}

function RunAdminLayout() {
  const { run } = useAdmin();
  const matches = useMatches();
  const pageTitle = [...matches].reverse().find((m) => m.handle?.title)?.handle.title;
  const wide = matches.some((m) => m.handle?.wide);
  const { pathname } = useLocation();
  const [failed, setFailed] = useState(null);
  const actionFailed = failed?.path === pathname;
  useEffect(() => onActionError((message) => setFailed({ path: window.location.pathname, message })), []);

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
              <Banner tone="danger">{failed.message || ADMIN_COPY.actionFailed}</Banner>
            </div>
          ) : null}
          <Outlet key={run.id} />
          <AppVersion />
        </div>
      </main>
    </div>
  );
}
