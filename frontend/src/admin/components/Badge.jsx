import styles from './Badge.module.css';

/** 상태 배지: 점 + 글자 + 옅은 바탕의 알약 (디자인 시스템 9-4). tone: danger | warning | success | info | neutral */
export default function Badge({ tone = 'neutral', children }) {
  return (
    <span className={`${styles.badge} ${styles[tone]}`}>
      <span className={styles.dot} aria-hidden="true" />
      {children}
    </span>
  );
}

/** 회차 상태 색 짝 (디자인 시스템 4-5): 산정 중 안내 / 검토 중 주의 / 확정 성공 / 참고 중립 */
export const RUN_TONE = { '산정 중': 'info', '검토 중': 'warning', 확정: 'success', 참고: 'neutral' };
/** 실행 상태 색 짝: 성공 / 실패 / 경고 / 실행 중 / 건너뜀 */
export const EXEC_TONE = { 성공: 'success', 실패: 'danger', 경고: 'warning', '실행 중': 'info', 건너뜀: 'neutral' };
