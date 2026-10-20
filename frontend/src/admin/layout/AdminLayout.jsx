import { useEffect, useState } from 'react';
import { Outlet, useLocation, useMatches } from 'react-router-dom';
import { useAdmin } from '../AdminProvider.jsx';
import { Banner } from '../components/Panel.jsx';
import { onActionError } from '../utils/actionError.js';
import { ADMIN_COPY } from '../copy.js';
import AdminTopBar from './AdminTopBar.jsx';
import SectionNav from './SectionNav.jsx';
import styles from './AdminLayout.module.css';

/** AD-00 공통 상단 + 본문. 위 두 줄(상단 바, 보조 탐색)은 스크롤해도 맨 위에 고정한다 (디자인 시스템 6-1). */
export default function AdminLayout() {
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
