import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../app/providers/AuthProvider.jsx';
import { useRun } from '../../app/providers/RunProvider.jsx';
import { ALL_GU, GU_LIST, ROLE } from '../../shared/constants.js';
import { buildMenu } from '../../shared/auth/permissions.js';
import { InfoHelp, SelectField } from '../components/FormControls.jsx';
import Notifications from './Notifications.jsx';
import styles from './TopBar.module.css';

/** US-00 공통 상단: 메뉴, 회차 선택, 구 선택, 알림, 계정 (디자인 시스템 7-1) */
export default function TopBar() {
  const { user, signOut } = useAuth();
  const { runs, run, setRunId, gu, setGu } = useRun();
  const navigate = useNavigate();
  const menu = buildMenu(user, run);
  const city = user.role === ROLE.CITY;

  const onLogout = async () => {
    await signOut();
    navigate('/login', { replace: true });
  };

  return (
    <header className={styles.bar}>
      <Link to="/candidates" className={styles.brand}>
        RADAR 보도 점검 우선순위
      </Link>
      <nav aria-label="주 메뉴" className={styles.nav}>
        {menu.map((m) => (m.items ? <MenuGroup key={m.key} group={m} /> : <NavItem key={m.key} to={m.to} label={m.label} />))}
      </nav>

      <div className={styles.tools}>
        <div className={styles.runBox}>
          <SelectField
            label="회차"
            id="run-select"
            value={run.id}
            onChange={setRunId}
            options={runs.map((r) => ({ value: r.id, label: `${r.name} · ${r.status}` }))}
          />
          <InfoHelp label="회차 도움말 보기" align="right">
            {`자료 기준일 ${run.dataRange} · 산정 기준 ${run.version} · 평가하지 못한 분야: ${run.unratedFields.join(', ')}`}
          </InfoHelp>
        </div>

        {city ? (
          <SelectField label="구" id="gu-select" value={gu} onChange={setGu} options={[ALL_GU, ...GU_LIST]} />
        ) : (
          <div className={styles.guFixed}>
            <span className={styles.fixedLabel}>구</span>
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

function NavItem({ to, label }) {
  return (
    <NavLink to={to} className={({ isActive }) => `${styles.navItem} ${isActive ? styles.active : ''}`}>
      {label}
    </NavLink>
  );
}

/** 보고서·기준정보처럼 아래 화면이 여럿인 메뉴. 누르면 목록이 열린다. */
function MenuGroup({ group }) {
  // 화면을 옮기면 목록이 저절로 닫히도록, 연 때의 주소를 기억한다
  const { pathname } = useLocation();
  const [openAt, setOpenAt] = useState(null);
  const open = openAt === pathname;
  const setOpen = (v) => setOpenAt((prev) => ((typeof v === 'function' ? v(prev === pathname) : v) ? pathname : null));
  const ref = useRef(null);
  const active = group.items.some((i) => pathname.startsWith(i.to));

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpenAt(null);
    };
    const onKey = (e) => e.key === 'Escape' && setOpenAt(null);
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div className={styles.group} ref={ref}>
      <button type="button" className={`${styles.navItem} ${active ? styles.active : ''}`} aria-expanded={open} aria-haspopup="true" onClick={() => setOpen((v) => !v)}>
        {group.label}
      </button>
      {open ? (
        <ul className={styles.dropdown}>
          {group.items.map((i) => (
            <li key={i.to}>
              <NavLink to={i.to} className={({ isActive }) => `${styles.dropItem} ${isActive ? styles.dropActive : ''}`}>
                {i.label}
              </NavLink>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
