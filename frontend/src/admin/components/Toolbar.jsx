import styles from './Toolbar.module.css';

/** 필터·동작 줄 (유형 B): 왼쪽에 필터, 오른쪽 끝에 동작 버튼 */
export default function Toolbar({ children, actions }) {
  return (
    <div className={styles.bar}>
      <div className={styles.filters}>{children}</div>
      {actions ? <div className={styles.actions}>{actions}</div> : null}
    </div>
  );
}
