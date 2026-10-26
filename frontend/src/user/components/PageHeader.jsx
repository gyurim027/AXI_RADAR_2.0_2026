import styles from './PageHeader.module.css';

/**
 * 화면 머리: (작은 파란 글씨) → 타이틀 → 서브 타이틀 → (오른쪽) 동작 (CM-00 6번 블록 순서)
 * eyebrow: 제목 위에 범위를 보인다 (예: 성남시 분당구)
 */
export default function PageHeader({ eyebrow, title, subtitle, children, compact = false }) {
  return (
    <header className={`${styles.head} ${compact ? styles.compact : ''}`}>
      <div className={styles.text}>
        {eyebrow && !compact ? <p className={styles.eyebrow}>{eyebrow}</p> : null}
        <h1 className={styles.title}>
          {title}
          {eyebrow && compact ? <span className={styles.scope}>{eyebrow}</span> : null}
        </h1>
        {subtitle ? <p className={styles.subtitle}>{subtitle}</p> : null}
      </div>
      {children ? <div className={styles.side}>{children}</div> : null}
    </header>
  );
}
