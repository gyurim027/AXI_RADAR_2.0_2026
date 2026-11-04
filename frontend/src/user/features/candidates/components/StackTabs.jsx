import { useEffect, useRef, useState } from 'react';
import { activeSection, scrollTarget } from '../stackNav.js';
import { prefersReducedMotion } from './mapUtils.js';
import styles from './StackTabs.module.css';

/**
 * 표·지도·확정 전환 막대 (1100px 미만, 쌓인 배치에서만). 누르면 그 구역으로 이동하고, 지금 보이는 구역을 표시한다.
 * sections: [{ key, label, ref, edge }] (edge: 'top'이면 맨 위로, 'bottom'이면 맨 아래로), containerRef: 위아래로 스크롤되는 영역
 * 지도 칸 높이는 '보이는 높이 − 막대 높이'로 맞춰(--stack-map-h) 지도 탭으로 이동하면 지도만 보이게 한다.
 */
export default function StackTabs({ label, sections, containerRef }) {
  const barRef = useRef(null);
  const [current, setCurrent] = useState(sections[0].key);

  useEffect(() => {
    const box = containerRef.current;
    if (!box) return undefined;
    const measure = () => {
      const barH = barRef.current?.offsetHeight ?? 0;
      box.style.setProperty('--stack-map-h', `${Math.max(0, box.clientHeight - barH)}px`);
      const base = box.getBoundingClientRect();
      const rects = sections.map((s) => {
        const r = s.ref.current?.getBoundingClientRect();
        return { key: s.key, top: r ? r.top - base.top : 0, bottom: r ? r.bottom - base.top : 0 };
      });
      setCurrent(
        activeSection(rects, barH, box.clientHeight, {
          atTop: box.scrollTop <= 2,
          atBottom: box.scrollTop + box.clientHeight >= box.scrollHeight - 2,
        }),
      );
    };
    measure();
    box.addEventListener('scroll', measure, { passive: true });
    const ro = new ResizeObserver(measure);
    ro.observe(box);
    window.addEventListener('resize', measure);
    return () => {
      box.removeEventListener('scroll', measure);
      ro.disconnect();
      window.removeEventListener('resize', measure);
      box.style.removeProperty('--stack-map-h');
    };
  }, [containerRef, sections]);

  const go = (s) => {
    const box = containerRef.current;
    if (!box) return;
    const r = s.ref.current?.getBoundingClientRect();
    const sectionTop = r ? box.scrollTop + (r.top - box.getBoundingClientRect().top) : 0;
    const top = scrollTarget({ edge: s.edge, sectionTop, barHeight: barRef.current?.offsetHeight ?? 0, scrollHeight: box.scrollHeight, clientHeight: box.clientHeight });
    box.scrollTo({ top, behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
  };

  return (
    <div ref={barRef} className={styles.bar} role="group" aria-label={label}>
      {sections.map((s) => (
        <button key={s.key} type="button" className={`${styles.btn} ${current === s.key ? styles.on : ''}`} aria-pressed={current === s.key} onClick={() => go(s)}>
          {s.label}
        </button>
      ))}
    </div>
  );
}
