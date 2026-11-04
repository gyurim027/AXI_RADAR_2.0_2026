import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { listProposals } from '../../api/reference.js';
import { useAuth } from '../../app/providers/AuthProvider.jsx';
import { useRun } from '../../app/providers/RunProvider.jsx';
import { ALL_GU, GU_LIST, ROLE } from '../../shared/constants.js';
import { useAsync } from '../../shared/hooks/useAsync.js';
import { activeGroup, buildMenu } from '../../shared/auth/permissions.js';
import { userMenuFilter } from '../serverRoutes.js';
import { dataYear, runOptionLabel } from '../../shared/utils/format.js';
import { InfoHelp, SelectField } from '../components/FormControls.jsx';
import Notifications from './Notifications.jsx';
import styles from './TopBar.module.css';

/** US-00 공통 상단: 메뉴, 점검 해 선택, 구 선택, 알림, 계정 (디자인 시스템 7-1). 하위 탭은 SubNav가 아래 줄에 보인다. */
export default function TopBar() {
  const { user, signOut } = useAuth();
  const { runs, run, setRunId, gu, setGu } = useRun();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const menu = buildMenu(user, userMenuFilter);
  const group = activeGroup(menu, pathname);
  const city = user.role === ROLE.CITY;
  // 승인 대기 건수 배지 (M-2). 시 도로과만 승인 대기를 본다.
  const pending = useAsync(() => (city ? listProposals() : Promise.resolve([])), [user.id, pathname]);
  const pendingCount = Array.isArray(pending.data) ? pending.data.length : 0;

  const onLogout = async () => {
    await signOut();
    navigate('/login', { replace: true });
  };

  return (
    <header className={styles.bar}>
      <Link to="/candidates" className={styles.brand}>
        RADAR<span className={styles.brandRest}> 보도 점검 우선순위</span>
      </Link>
      <nav aria-label="주 메뉴" className={styles.nav}>
        {menu.map((m) => {
          const to = m.to || m.items[0].to;
          const active = m.items ? group?.key === m.key : pathname.startsWith(m.to);
          return (
            <NavLink key={m.key} to={to} className={`${styles.navItem} ${active ? styles.active : ''}`} aria-current={active ? 'page' : undefined}>
              {m.label}
              {m.badge === 'approvals' && pendingCount > 0 ? (
                <span className={styles.badge} aria-label={`${pendingCount}건`}>
                  {pendingCount}
                </span>
              ) : null}
            </NavLink>
          );
        })}
      </nav>

      <div className={styles.tools}>
        <div className={styles.runBox}>
          <SelectField
            label="점검 연도"
            id="run-select"
            value={run.id}
            onChange={setRunId}
            options={runs.map((r) => ({ value: r.id, label: runOptionLabel(r) }))}
          />
          <InfoHelp label="자료 기준 보기" text="자료 기준" iconless>
            {[
              '1년치를 계산한 점검 순위입니다. 반기 계산 결과는 참고용으로만 사용해 주세요.',
              run.dataRange ? `${dataYear(run.dataRange)}년 자료 기준 · 자료 기준일 ${run.dataRange}` : null,
              run.version ? `산정 기준 ${run.version}` : null,
              run.unratedFields?.length ? `평가하지 못한 분야: ${run.unratedFields.join(', ')}. 자료가 없어 평가하지 못한 분야이며 0점으로 처리하지 않았습니다.` : null,
            ].filter(Boolean).join(' · ')}
          </InfoHelp>
        </div>

        {city ? (
          <SelectField label="구" hideLabel id="gu-select" value={gu} onChange={setGu} options={[ALL_GU, ...GU_LIST]} />
        ) : (
          <div className={styles.guFixed}>
            <span>{user.gu}</span>
          </div>
        )}

        <Notifications />

        <div className={styles.account}>
          <span className={styles.org}>{user.org}</span>
          <button type="button" className={styles.logout} onClick={onLogout}>
            로그아웃
          </button>
        </div>
      </div>
    </header>
  );
}
