import styles from './PageHeader.module.css';

/** 화면 머리: 타이틀 → 서브 타이틀. 주요 동작 버튼은 제목 줄 오른쪽 끝이다 (디자인 시스템 6-2) */
export default function PageHeader({ title, subtitle, children, meta }) {
  return (
    <header className={styles.head}>
      <div className={styles.text}>
        <div className={styles.titleRow}>
          <h1 className={styles.title}>{title}</h1>
          {meta}
        </div>
        {subtitle ? <p className={styles.subtitle}>{subtitle}</p> : null}
      </div>
      {children ? <div className={styles.side}>{children}</div> : null}
    </header>
  );
}
