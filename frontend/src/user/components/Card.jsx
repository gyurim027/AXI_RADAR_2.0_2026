import styles from './Card.module.css';

/**
 * 카드: 같은 종류의 정보를 한 덩어리로 묶는다.
 * variant: plain(흰 바탕, 기본) | soft(옅은 파랑, 가장 중요한 요약) | subtle(옅은 회색, 보조 정보)
 * title: 카드 제목(14px 굵게), aside: 제목 줄 오른쪽 끝의 작은 요소(예: ⓘ)
 */
export default function Card({ variant = 'plain', title, aside, className = '', children, ...rest }) {
  return (
    <section className={`${styles.card} ${styles[variant]} ${className}`} {...rest}>
      {title || aside ? (
        <header className={styles.head}>
          {title ? <h3 className={styles.title}>{title}</h3> : <span />}
          {aside ? <div className={styles.aside}>{aside}</div> : null}
        </header>
      ) : null}
      <div className={styles.body}>{children}</div>
    </section>
  );
}
