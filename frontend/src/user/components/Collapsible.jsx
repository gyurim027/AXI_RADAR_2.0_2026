import { useId } from 'react';
import Icon from './Icon.jsx';
import styles from './Collapsible.module.css';

/** 접고 펼치는 묶음. 접은 상태에서도 제목과 개수가 보인다 (디자인 시스템 11-4). */
export default function Collapsible({ title, description, accent = false, open, onToggle, children }) {
  const id = useId();
  return (
    <section className={`${styles.box} ${accent ? styles.accent : ''}`}>
      <h3 className={styles.head}>
        <button type="button" className={styles.btn} aria-expanded={open} aria-controls={id} onClick={onToggle}>
          <span>{title}</span>
          <Icon name={open ? 'chevronUp' : 'chevronDown'} size={18} />
        </button>
      </h3>
      {description ? <p className={styles.desc}>{description}</p> : null}
      {open ? (
        <div id={id} className={styles.body}>
          {children}
        </div>
      ) : null}
    </section>
  );
}
