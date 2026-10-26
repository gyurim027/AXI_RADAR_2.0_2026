import { NavLink, useLocation } from 'react-router-dom';
import { ADMIN_COPY } from '../copy.js';
import { setDensity, useDensity } from '../utils/density.js';
import styles from './SectionNav.module.css';

/** 보조 탐색 (44px): 고른 1단계 메뉴 아래 화면들. 화면이 하나뿐인 대시보드에는 두지 않는다. */
export default function SectionNav() {
  const { pathname } = useLocation();
  const density = useDensity();
  const group = ADMIN_COPY.menu.find((m) => m.items && m.items.some((i) => pathname.startsWith(i.to)));
  if (!group) return null;
  return (
    <nav aria-label={ADMIN_COPY.sectionMenuLabel} className={styles.nav}>
      {group.items.map((i) => (
        <NavLink key={i.to} to={i.to} className={({ isActive }) => `${styles.item} ${isActive ? styles.active : ''}`}>
          {i.label}
        </NavLink>
      ))}
      <div className={styles.density} role="group" aria-label={ADMIN_COPY.density.label}>
        <span className={styles.densityLabel}>{ADMIN_COPY.density.label}</span>
        {['normal', 'compact'].map((d) => (
          <button key={d} type="button" className={`${styles.densityBtn} ${density === d ? styles.densityOn : ''}`} aria-pressed={density === d} onClick={() => setDensity(d)}>
            {ADMIN_COPY.density[d]}
          </button>
        ))}
      </div>
    </nav>
  );
}
