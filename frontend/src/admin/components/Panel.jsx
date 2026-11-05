import styles from './Panel.module.css';

/** 흰 패널 (디자인 시스템 6-2). 그림자 없이 1px 연한 선만 쓴다. */
export default function Panel({ title, description, actions, children, className = '', 'aria-label': ariaLabel, 'data-guide': guide, padded = true }) {
  return (
    <section className={`${styles.panel} ${className}`} aria-label={ariaLabel} data-guide={guide}>
      {title || actions ? (
        <div className={`${styles.head} ${padded ? '' : styles.headPad}`}>
          <div>
            {title ? <h2 className={styles.title}>{title}</h2> : null}
            {description ? <p className={styles.desc}>{description}</p> : null}
          </div>
          {actions ? <div className={styles.actions}>{actions}</div> : null}
        </div>
      ) : null}
      <div className={padded ? styles.body : styles.flush}>{children}</div>
    </section>
  );
}

/** 안내 띠 (디자인 시스템 9-5). tone: info | warning | danger | success */
export function Banner({ tone = 'info', children, role }) {
  return (
    <div className={`${styles.banner} ${styles[`banner_${tone}`]}`} role={role || (tone === 'danger' ? 'alert' : 'status')}>
      {children}
    </div>
  );
}
