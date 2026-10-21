import Icon from '../../user/components/Icon.jsx';
import styles from './Button.module.css';

/**
 * 어드민 버튼 (디자인 시스템 9-1)
 * variant: primary(화면에서 가장 중요한 행동 하나) | soft | secondary | danger | text(표 안 행동)
 * compact: 표 안 36px. loading: 버튼 폭은 그대로 두고 진행 표시를 넣는다.
 */
export default function Button({ variant = 'secondary', compact = false, loading = false, disabled = false, children, className = '', type = 'button', ...rest }) {
  return (
    <button
      type={type}
      className={`${styles.btn} ${styles[variant]} ${compact ? styles.compact : ''} ${loading ? styles.loading : ''} ${className}`}
      aria-busy={loading || undefined}
      disabled={disabled || loading}
      {...rest}
    >
      <span className={styles.label}>{children}</span>
      {loading ? <Icon name="spinner" size={20} className={styles.spin} /> : null}
    </button>
  );
}
