import { useRef } from 'react';
import styles from './Tabs.module.css';

/** 탭 (WAI-ARIA tablist). 화살표 키로 옮긴다. panel은 호출하는 쪽이 role="tabpanel"로 만든다. */
export default function Tabs({ tabs, value, onChange, label, idPrefix = 'tab' }) {
  const refs = useRef({});
  const move = (e, idx) => {
    let next = null;
    if (e.key === 'ArrowRight') next = (idx + 1) % tabs.length;
    if (e.key === 'ArrowLeft') next = (idx - 1 + tabs.length) % tabs.length;
    if (e.key === 'Home') next = 0;
    if (e.key === 'End') next = tabs.length - 1;
    if (next == null) return;
    e.preventDefault();
    onChange(tabs[next].key);
    refs.current[tabs[next].key]?.focus();
  };
  return (
    <div className={styles.list} role="tablist" aria-label={label}>
      {tabs.map((t, i) => (
        <button
          key={t.key}
          ref={(el) => {
            refs.current[t.key] = el;
          }}
          id={`${idPrefix}-${t.key}`}
          type="button"
          role="tab"
          aria-selected={value === t.key}
          aria-controls={`${idPrefix}-panel`}
          tabIndex={value === t.key ? 0 : -1}
          className={`${styles.tab} ${value === t.key ? styles.active : ''}`}
          onClick={() => onChange(t.key)}
          onKeyDown={(e) => move(e, i)}
        >
          {t.label}
          {t.count != null ? <span className={styles.count}>{t.count}</span> : null}
        </button>
      ))}
    </div>
  );
}
