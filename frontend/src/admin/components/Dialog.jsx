import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import styles from './Dialog.module.css';

const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

/**
 * 대화상자 (유형 E). 폭 480(sm) 또는 640(md). 바깥을 눌러도 닫히지 않고, 취소 버튼과 Esc로 닫는다.
 * 열 때 포커스를 안으로 옮기고 닫으면 열었던 자리로 돌려준다 (디자인 시스템 12장).
 */
export default function Dialog({ title, titleId, size = 'sm', onClose, closeLabel, children, footer, subtitle }) {
  const ref = useRef(null);
  const previous = useRef(null);

  useEffect(() => {
    previous.current = document.activeElement;
    const node = ref.current;
    (node?.querySelector(FOCUSABLE) || node)?.focus();
    const onKey = (e) => {
      if (e.key === 'Escape' && onClose) {
        e.stopPropagation();
        onClose();
      }
      if (e.key === 'Tab' && node) {
        const items = [...node.querySelectorAll(FOCUSABLE)];
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      previous.current?.focus?.();
    };
  }, [onClose]);

  return createPortal(
    <div className={styles.scrim}>
      <div ref={ref} className={`${styles.dialog} ${size === 'md' ? styles.md : styles.sm}`} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}>
        {onClose && closeLabel ? (
          <button type="button" className={styles.close} onClick={onClose} aria-label={closeLabel}>
            ×
          </button>
        ) : null}
        <h2 id={titleId} className={styles.title}>
          {title}
        </h2>
        {subtitle ? <p className={styles.subtitle}>{subtitle}</p> : null}
        <div className={styles.body}>{children}</div>
        {footer ? <div className={styles.footer}>{footer}</div> : null}
      </div>
    </div>,
    document.body,
  );
}
