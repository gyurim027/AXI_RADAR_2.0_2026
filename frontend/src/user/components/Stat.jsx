import styles from './Stat.module.css';

/**
 * 핵심 수치 한 개: 이름(12px 보조색) 아래에 값(20px 굵게)과 단위, 꼬리표를 한 줄로 두고, 선택으로 0~100 막대를 붙인다.
 * tone(top | mid | rest)은 막대 색이며 값은 늘 숫자로도 보인다.
 */
export default function Stat({ label, aside, value, unit, chip, meter, tone = 'rest' }) {
  return (
    <div className={styles.stat}>
      <div className={styles.labelRow}>
        <span className={styles.label}>{label}</span>
        {aside}
      </div>
      <div className={styles.valueRow}>
        <span className={`${styles.value} num`}>
          {value}
          {unit ? <span className={styles.unit}>{unit}</span> : null}
        </span>
        {chip ? <span className={styles.chip}>{chip}</span> : null}
      </div>
      {meter != null ? (
        <div className={styles.track} aria-hidden="true">
          <div className={`${styles.fill} ${styles[tone]}`} style={{ width: `${Math.max(0, Math.min(100, meter))}%` }} />
        </div>
      ) : null}
    </div>
  );
}
