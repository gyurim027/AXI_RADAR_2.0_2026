import { Link } from 'react-router-dom';
import styles from './StatTile.module.css';

/**
 * 지표 타일: 숫자(24px 굵게)와 단위, 그 아래에 이름(14px 보조색). 값을 모르면 '-'를 보인다.
 * to가 있으면 타일 전체가 그 상태로 거른 화면으로 가는 링크다.
 */
export default function StatTile({ label, value, unit, to }) {
  const inner = (
    <>
      <span className={styles.valueRow}>
        <span className={styles.value}>{value === null || value === undefined ? '-' : value}</span>
        {unit ? <span className={styles.unit}>{unit}</span> : null}
      </span>
      <span className={styles.label}>{label}</span>
    </>
  );
  return to ? (
    <Link to={to} className={`${styles.tile} ${styles.link}`}>
      {inner}
    </Link>
  ) : (
    <div className={styles.tile}>{inner}</div>
  );
}

/** 지표 타일 묶음: 타일 사이에 세로선을 둔다. */
export function StatTiles({ children }) {
  return <div className={styles.tiles}>{children}</div>;
}
