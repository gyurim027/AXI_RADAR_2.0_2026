import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import Icon from './Icon.jsx';
import styles from './Modal.module.css';

const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

/**
 * 확인 창. 폭 520px, 뒤에 어두운 막. 바깥을 눌러도 닫히지 않는다 (디자인 시스템 8장).
 * closeLabel을 주면 오른쪽 위에 ×가 생기고, Esc로도 닫힌다.
 */
export default function Modal({ title, titleId, onClose, closeLabel, children, role = 'dialog' }) {
  const ref = useRef(null);
  const previous = useRef(null);

  useEffect(() => {
    previous.current = document.activeElement;
    const node = ref.current;
    const first = node?.querySelector(FOCUSABLE);
    (first || node)?.focus();
    const onKey = (e) => {
      if (e.key === 'Escape' && onClose && closeLabel) {
        e.stopPropagation();
        onClose();
      }
      if (e.key === 'Tab' && node) {
        const items = [...node.querySelectorAll(FOCUSABLE)];
        if (!items.length) return;
        const firstEl = items[0];
        const lastEl = items[items.length - 1];
        if (e.shiftKey && document.activeElement === firstEl) {
          e.preventDefault();
          lastEl.focus();
        } else if (!e.shiftKey && document.activeElement === lastEl) {
          e.preventDefault();
          firstEl.focus();
        }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      previous.current?.focus?.();
    };
  }, [onClose, closeLabel]);

  return createPortal(
    <div className={styles.scrim}>
      <div ref={ref} className={styles.modal} role={role} aria-modal="true" aria-labelledby={titleId} tabIndex={-1}>
        {onClose && closeLabel ? (
          <button type="button" className={styles.close} onClick={onClose} aria-label={closeLabel}>
            <Icon name="close" size={20} />
          </button>
        ) : null}
        <h2 id={titleId} className={styles.title}>
          {title}
        </h2>
        {children}
      </div>
    </div>,
    document.body,
  );
}
