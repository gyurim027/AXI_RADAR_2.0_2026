import Icon from './Icon.jsx';
import styles from './Callout.module.css';

/**
 * 안내 상자: 문장 하나를 아이콘과 함께 강조한다.
 * tone: ai(AI가 만든 설명·요청 문장, 반짝이) | info(안내) | warn(주의, 예: 작년에 제외·보류한 후보)
 */
export default function Callout({ tone = 'info', children, className = '' }) {
  return (
    <p className={`${styles.callout} ${styles[tone]} ${className}`}>
      <Icon name={tone === 'ai' ? 'sparkle' : 'info'} size={16} className={styles.icon} />
      <span>{children}</span>
    </p>
  );
}
