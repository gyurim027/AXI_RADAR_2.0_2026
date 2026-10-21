import { useEffect } from 'react';
import { Outlet, useMatches } from 'react-router-dom';
import { RUN_STATUS } from '../../shared/constants.js';
import { useAuth } from '../../app/providers/AuthProvider.jsx';
import { useRun } from '../../app/providers/RunProvider.jsx';
import TopBar from './TopBar.jsx';
import StatusBand from './StatusBand.jsx';
import ViewAsBand from './ViewAsBand.jsx';
import styles from './UserLayout.module.css';

/** US-00 공통 상단 + 상태 띠 + 본문. 순위 안내는 각 화면 머리(PageHeader)가 보인다. */
export default function UserLayout() {
  const { run } = useRun();
  const { user } = useAuth();
  const matches = useMatches();
  const edge = matches.some((m) => m.handle?.edgeToEdge); // 지도가 화면 끝까지 차는 화면
  const pageTitle = [...matches].reverse().find((m) => m.handle?.title)?.handle.title;

  // 화면마다 브라우저 탭 제목을 다르게 한다 (스크린 리더와 탭 구분용)
  useEffect(() => {
    document.title = pageTitle ? `${pageTitle} · RADAR 보도 점검 우선순위` : 'RADAR 보도 점검 우선순위';
  }, [pageTitle]);

  return (
    <div className={styles.shell}>
      <a href="#main" className={styles.skip}>
        본문 바로가기
      </a>
      {user.readOnly ? <ViewAsBand /> : null}
      <TopBar />
      {run.status !== RUN_STATUS.REVIEW ? <StatusBand run={run} /> : null}
      <main className={`${styles.main} ${edge ? styles.mainEdge : ''}`} id="main" tabIndex={-1}>
        <div className={edge ? styles.edge : styles.content}>
          <Outlet />
        </div>
      </main>
    </div>
  );
}
