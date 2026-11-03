import { useEffect, useState } from 'react';
import { activeSection } from '../stackNav.js';
import { prefersReducedMotion } from './mapUtils.js';
import styles from './StackTabs.module.css';

/**
 * 표·지도 전환 막대 (1100px 미만, 쌓인 배치에서만). 누르면 그 구역으로 이동하고, 지금 보이는 구역을 표시한다.
 * sections: [{ key, label, ref }], containerRef: 위아래로 스크롤되는 영역
 */
export default function StackTabs({ label, sections, containerRef }) {
  const [current, setCurrent] = useState(sections[0].key);

  useEffect(() => {
    const box = containerRef.current;
    if (!box) return undefined;
    const measure = () => {
      const base = box.getBoundingClientRect();
      const rects = sections.map((s) => {
        const r = s.ref.current?.getBoundingClientRect();
        return { key: s.key, top: r ? r.top - base.top : 0, bottom: r ? r.bottom - base.top : 0 };
      });
      setCurrent(activeSection(rects, 0, box.clientHeight));
    };
    measure();
    box.addEventListener('scroll', measure, { passive: true });
    window.addEventListener('resize', measure);
    return () => {
      box.removeEventListener('scroll', measure);
      window.removeEventListener('resize', measure);
    };
  }, [containerRef, sections]);

  const go = (s) => s.ref.current?.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' });

  return (
    <div className={styles.bar} role="group" aria-label={label}>
      {sections.map((s) => (
        <button key={s.key} type="button" className={`${styles.btn} ${current === s.key ? styles.on : ''}`} aria-pressed={current === s.key} onClick={() => go(s)}>
          {s.label}
        </button>
      ))}
    </div>
  );
}
