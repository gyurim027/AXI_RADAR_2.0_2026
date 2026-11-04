import Icon from './Icon.jsx';
import styles from './Tag.module.css';

/**
 * 꼬리표(태그). tone: neutral | info | high | mid | low | gray | accent | sky | lavender
 * accent·sky·lavender는 후보 표의 조건 구분색이다(디자인 시스템 14장).
 * 색만으로 뜻을 전하지 않도록 늘 글자를 같이 쓴다.
 * onRemove가 있으면 ×로 지우는 꼬리표가 된다 (클릭 칸 24px 이상).
 */
export default function Tag({ tone = 'neutral', children, onRemove, removeLabel, small = false, className = '', title }) {
  return (
    <span className={`${styles.tag} ${styles[tone]} ${small ? styles.small : ''} ${className}`} title={title}>
      <span>{children}</span>
      {onRemove ? (
        <button type="button" className={styles.remove} onClick={onRemove} aria-label={removeLabel || '필터 지우기'}>
          <Icon name="close" size={14} />
        </button>
      ) : null}
    </span>
  );
}

/** 표 안 상태 배지: 옅은 바탕에 글자만 있는 알약 모양 (디자인 시스템 14장) */
export function Badge({ tone = 'neutral', children }) {
  return <span className={`${styles.badge} ${styles[tone]}`}>{children}</span>;
}
