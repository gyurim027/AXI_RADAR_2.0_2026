import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { useWelcome } from '../../user/features/welcome/useWelcome.js';
import { GUIDE_COPY } from './guideConfig.js';
import { getAvailable, requestGuide, subscribe } from './guideStore.js';
import styles from './HelpMenu.module.css';

/** 계정 영역의 `?` 버튼. 누르면 `이 화면 안내 다시 보기`와 `서비스 소개 보기` 목록이 열린다. 상단 메뉴 탭이 아니다. */
export default function HelpMenu() {
  const [open, setOpen] = useState(false);
  const available = useSyncExternalStore(subscribe, getAvailable);
  const { open: openWelcome } = useWelcome();
  const wrapRef = useRef(null);
  const listRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    listRef.current?.querySelector('button')?.focus();
    const onDoc = (e) => { if (!wrapRef.current?.contains(e.target)) setOpen(false); };
    const onKey = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); setOpen(false); wrapRef.current?.querySelector('button')?.focus(); }
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        const items = [...(listRef.current?.querySelectorAll('button') || [])];
        if (!items.length) return;
        e.preventDefault();
        const at = items.indexOf(document.activeElement);
        const next = e.key === 'ArrowDown' ? (at + 1) % items.length : (at - 1 + items.length) % items.length;
        items[next].focus();
      }
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const pick = (fn) => () => { setOpen(false); fn(); };

  return (
    <div className={styles.wrap} ref={wrapRef}>
      <button type="button" className={styles.btn} aria-haspopup="menu" aria-expanded={open} aria-label={GUIDE_COPY.helpMenuLabel} title={GUIDE_COPY.helpMenuLabel} onClick={() => setOpen((v) => !v)}>
        ?
      </button>
      {open ? (
        <div className={styles.list} role="menu" ref={listRef}>
          {available ? <button type="button" role="menuitem" className={styles.item} onClick={pick(requestGuide)}>{GUIDE_COPY.replayScreen}</button> : null}
          <button type="button" role="menuitem" className={styles.item} onClick={pick(openWelcome)}>{GUIDE_COPY.openWelcome}</button>
        </div>
      ) : null}
    </div>
  );
}
