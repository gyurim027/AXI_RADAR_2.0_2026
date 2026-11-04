import { DECISION } from '../../../../shared/constants.js';
import { LIST } from '../copy.js';
import styles from './KpiCards.module.css';

/**
 * 1 KPI 카드. 카드 자체가 표의 결정 상태 필터다.
 * 처음에는 '전체'가 선택돼 있다. 선택한 카드를 다시 누르면 '전체'로 돌아간다.
 */
export default function KpiCards({ counts, active, onPick }) {
  const cells = [
    { key: '', label: LIST.kpi.total, value: counts.total },
    { key: DECISION.NONE, label: LIST.kpi.none, value: counts.none },
    { key: DECISION.TARGET, label: LIST.kpi.target, value: counts.target },
    { key: DECISION.HOLD, label: LIST.kpi.hold, value: counts.hold },
    { key: DECISION.EXCLUDE, label: LIST.kpi.exclude, value: counts.exclude },
  ];
  return (
    <ul className={styles.list} aria-label={LIST.kpiLabel}>
      {cells.map((c) => {
        const on = active === c.key;
        return (
          <li key={c.label}>
            <button type="button" className={`${styles.card} ${on ? styles.on : ''}`} aria-pressed={on} onClick={() => onPick(on && c.key ? '' : c.key)}>
              <span className={styles.label}>{c.label}</span>
              <span className={styles.valueRow}>
                <span className={`${styles.value} num`}>{c.value}</span>
                <span className={styles.unit}>{LIST.kpiUnit}</span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
