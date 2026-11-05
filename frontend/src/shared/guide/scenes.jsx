import styles from './GuideTour.module.css';

function Cursor({ variant }) {
  return (
    <svg className={`${styles.cursor} ${styles[`cur_${variant}`]}`} width="22" height="22" viewBox="0 0 22 22" aria-hidden="true" focusable="false">
      <path d="M3 2 L3 17 L7.2 13.2 L10 19 L12.6 17.8 L9.8 12.2 L15.5 12 Z" fill="#15182b" stroke="#fff" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
}
const Ripple = ({ variant }) => <span className={`${styles.ripple} ${styles[`rip_${variant}`]}`} aria-hidden="true" />;

/** 카드 위 미니 장면. 실제 화면을 찍은 그림이 아니라 눌러서 쓰는 모습을 단순하게 그린 모형이다. */
export default function Scene({ name, label }) {
  return (
    <div className={styles.stage} aria-hidden="true">
      {name === 'select' ? (
        <>
          <div className={styles.sel}><span>2027 연간</span><i className={styles.caret} /></div>
          <div className={styles.dd}><b>2028 연간</b><b className={styles.ddOn}>2027 연간</b><b>2026 연간</b></div>
          <Ripple variant="select" /><Cursor variant="select" />
        </>
      ) : null}
      {name === 'menu' ? (
        <>
          <div className={styles.pill}>{label || '필터'}</div>
          <div className={styles.panel}><b>보호구역</b><b>민원 쏠림</b><b>자료 신뢰도</b></div>
          <Ripple variant="menu" /><Cursor variant="menu" />
        </>
      ) : null}
      {name === 'row' ? (
        <>
          <div className={styles.rows}><b /><b className={styles.rowOn} /><b /></div>
          <div className={styles.pop}><i /><i /><i className={styles.popShort} /></div>
          <Ripple variant="row" /><Cursor variant="row" />
        </>
      ) : null}
      {name === 'button' ? (
        <>
          <div className={styles.bar}><i /><i className={styles.barShort} /></div>
          <div className={styles.cta}>{label || '확인'}</div>
          <span className={styles.check}>✓</span>
          <Ripple variant="button" /><Cursor variant="button" />
        </>
      ) : null}
      {name === 'map' ? (
        <>
          <div className={styles.mapGrid}>{Array.from({ length: 12 }, (_, i) => <b key={i} className={i % 5 === 1 || i === 6 ? styles.hot : ''} />)}</div>
          <div className={styles.key}>Ctrl</div>
          <Cursor variant="map" />
        </>
      ) : null}
    </div>
  );
}
