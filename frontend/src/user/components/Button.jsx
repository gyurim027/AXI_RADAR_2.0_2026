import Icon from './Icon.jsx';
import styles from './Button.module.css';

/**
 * variant: primary(기본, 화면의 주된 행동 하나) | soft(옅은 파랑, 보조) | neutral(회색, 아직 준비가 덜 됐음을 보이지만 누를 수 있다) | danger(옅은 빨강) | text(텍스트 링크)
 * loading: 버튼 안에 진행 표시를 넣고 폭은 그대로 둔다 (디자인 시스템 12장)
 */
export default function Button({ variant = 'primary', loading = false, children, className = '', type = 'button', ...rest }) {
  return (
    <button
      type={type}
      className={`${styles.btn} ${styles[variant]} ${loading ? styles.loading : ''} ${className}`}
      aria-busy={loading || undefined}
      {...rest}
    >
      <span className={styles.label}>{children}</span>
      {loading ? <Icon name="spinner" size={20} className={styles.spin} /> : null}
    </button>
  );
}
