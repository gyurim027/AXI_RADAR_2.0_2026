import styles from './Stepper.module.css';

/**
 * 회차 단계 표시: 지금 단계를 강조하고, 지난 단계는 채워서 보인다. 색뿐 아니라 글자와 순서 번호로도 읽힌다.
 * steps: 단계 이름 목록, current: 지금 단계 이름 (목록에 없으면 아무 단계도 강조하지 않는다)
 */
export default function Stepper({ steps, current, label }) {
  const at = steps.indexOf(current);
  return (
    <ol className={styles.steps} aria-label={label}>
      {steps.map((s, i) => (
        <li key={s} className={`${styles.step} ${i < at ? styles.done : ''} ${i === at ? styles.now : ''}`} aria-current={i === at ? 'step' : undefined}>
          <span className={styles.num} aria-hidden="true">
            {i + 1}
          </span>
          <span className={styles.name}>{s}</span>
        </li>
      ))}
    </ol>
  );
}
