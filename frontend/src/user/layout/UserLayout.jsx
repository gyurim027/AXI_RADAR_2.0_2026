import { useEffect } from 'react';
import { Link, Outlet, useLocation, useMatches, useNavigate } from 'react-router-dom';
import { backendAuthEnabled, i07BackendEnabled } from '../../api/backend.js';
import NotConnected from '../components/NotConnected.jsx';
import { ROLE } from '../../shared/constants.js';
import { RUN_STATUS } from '../../shared/constants.js';
import { useAuth } from '../../app/providers/AuthProvider.jsx';
import { useRun } from '../../app/providers/RunProvider.jsx';
import TopBar from './TopBar.jsx';
import SubNav from './SubNav.jsx';
import StatusBand from './StatusBand.jsx';
import ViewAsBand from './ViewAsBand.jsx';
import styles from './UserLayout.module.css';
import bar from './TopBar.module.css';

/** US-00 공통 상단 + 상태 띠 + 본문. 순위 안내는 각 화면 머리(PageHeader)가 보인다. */
export default function UserLayout() {
  // 서버 연결 모드에서는 회차·가짜 데이터를 쓰지 않는 최소 틀만 쓴다. 연결된 화면(승인 대기)만 열고 나머지는 안내를 보인다.
  if (backendAuthEnabled) return <ServerUserLayout />;
  return <RunUserLayout />;
}

// 승인 작업은 회차·점수 생성에 의존하지 않는다. 기존 승인 화면과 공통 스타일을 사용한다.
function ServerUserLayout() {
  const { user, signOut } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const approvals = i07BackendEnabled && user.role === ROLE.CITY;
  const onApprovals = pathname.replace(/\/$/, '') === '/reference/approvals';
  useEffect(() => { document.title = 'RADAR 보도 점검 우선순위'; }, []);
  const logout = async () => { await signOut(); navigate('/login', { replace: true }); };
  return (
    <div className={styles.shell}>
      <a href="#main" className={styles.skip}>본문 바로가기</a>
      <header className={bar.bar}>
        <Link to={approvals ? '/reference/approvals' : '/'} className={bar.brand}>RADAR 보도 점검 우선순위</Link>
        {approvals ? <nav aria-label="주 메뉴"><Link to="/reference/approvals">승인 대기</Link></nav> : null}
        <div className={bar.account}><span>{user.org}</span><button type="button" className={bar.logout} onClick={logout}>로그아웃</button></div>
      </header>
      <main className={styles.main} id="main" tabIndex={-1}><div className={styles.content}>{approvals && onApprovals ? <Outlet /> : <NotConnected role={user.role} />}</div></main>
    </div>
  );
}

function RunUserLayout() {
  const { run } = useRun();
  const { user } = useAuth();
  const matches = useMatches();
  const edge = matches.some((m) => m.handle?.edgeToEdge); // 지도가 화면 끝까지 차는 화면
  const reading = matches.some((m) => m.handle?.reading); // 보고서·참고 자료: 본문 폭 하나
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
      <SubNav />
      {run.status !== RUN_STATUS.REVIEW ? <StatusBand run={run} /> : null}
      <main className={`${styles.main} ${edge ? styles.mainEdge : ''}`} id="main" tabIndex={-1}>
        <div className={edge ? styles.edge : `${styles.content} ${reading ? styles.reading : ''}`}>
          <Outlet />
        </div>
      </main>
    </div>
  );
}
