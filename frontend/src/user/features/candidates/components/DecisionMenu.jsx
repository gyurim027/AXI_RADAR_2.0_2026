import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import Icon from '../../../components/Icon.jsx';
import { DECISION } from '../../../../shared/constants.js';
import styles from './DecisionMenu.module.css';

const CHOICES = [DECISION.TARGET, DECISION.EXCLUDE, DECISION.HOLD];

/**
 * 표의 결정 상태 칸 버튼 + 메뉴. 고르면 기존 사유 입력 창이 열린다.
 * 도로관리팀 · 검토 중 회차 · 구 확정 전에만 쓴다. 그 밖에는 글자만 보인다 (CM-00 10번).
 * 메뉴는 화면 맨 위층으로 띄워 표의 스크롤 영역에 잘리지 않게 한다.
 */
export default function DecisionMenu({ value, label, onSelect }) {
  const btnRef = useRef(null);
  const menuRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  useLayoutEffect(() => {
    if (!open || !btnRef.current) return;
    const r = btnRef.current.getBoundingClientRect();
    setPos({ top: r.bottom + 4, left: Math.max(8, Math.min(r.left, window.innerWidth - 168)) });
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    menuRef.current?.querySelector('button:not([disabled])')?.focus();
    const close = () => setOpen(false);
    const onDoc = (e) => {
      if (!menuRef.current?.contains(e.target) && !btnRef.current?.contains(e.target)) close();
    };
    const onKey = (e) => {
      if (e.key === 'Escape') {
        close();
        btnRef.current?.focus();
      }
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    window.addEventListener('scroll', close, true);
    window.addEventListener('resize', close);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('scroll', close, true);
      window.removeEventListener('resize', close);
    };
  }, [open]);

  const onMenuKey = (e) => {
    const items = [...menuRef.current.querySelectorAll('button:not([disabled])')];
    const i = items.indexOf(document.activeElement);
    if (e.key === 'ArrowDown') items[(i + 1) % items.length]?.focus();
    else if (e.key === 'ArrowUp') items[(i - 1 + items.length) % items.length]?.focus();
    else return;
    e.preventDefault();
  };

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        className={styles.btn}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`${label} (지금 ${value})`}
        onClick={(e) => {
          e.stopPropagation(); // 행 선택과 따로 동작한다
          setOpen((v) => !v);
        }}
        onKeyDown={(e) => e.stopPropagation()}
      >
        <span>{value}</span>
        <Icon name="chevronDown" size={14} />
      </button>
      {open
        ? createPortal(
            <ul ref={menuRef} role="menu" className={styles.menu} style={{ top: pos.top, left: pos.left }} onKeyDown={onMenuKey}>
              {CHOICES.map((c) => (
                <li key={c} role="none">
                  <button
                    type="button"
                    role="menuitem"
                    className={styles.item}
                    disabled={c === value}
                    onClick={() => {
                      setOpen(false);
                      onSelect(c);
                    }}
                  >
                    {c}
                  </button>
                </li>
              ))}
            </ul>,
            document.body,
          )
        : null}
    </>
  );
}
