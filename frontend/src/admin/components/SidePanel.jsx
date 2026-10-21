import { useEffect, useRef } from 'react';
import styles from './SidePanel.module.css';

/** 오른쪽 옆 패널 (유형 D). 열면 구역 패널이 그만큼 줄어든다. 닫으면 열었던 자리로 포커스를 돌려준다. */
export default function SidePanel({ title, titleId, onClose, closeLabel, children }) {
  const ref = useRef(null);
  const previous = useRef(null);
  useEffect(() => {
    previous.current = document.activeElement;
    ref.current?.focus();
    const onKey = (e) => e.key === 'Escape' && onClose?.();
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      previous.current?.focus?.();
    };
  }, [onClose]);
  return (
    <aside ref={ref} className={styles.panel} aria-labelledby={titleId} tabIndex={-1}>
      <div className={styles.head}>
        <h2 id={titleId} className={styles.title}>
          {title}
        </h2>
        <button type="button" className={styles.close} onClick={onClose} aria-label={closeLabel}>
          ×
        </button>
      </div>
      <div className={styles.body}>{children}</div>
    </aside>
  );
}
