import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { GUIDE_COPY } from './guideConfig.js';
import { clampIndex, placeCoach } from './guideLogic.js';
import Scene from './scenes.jsx';
import styles from './GuideTour.module.css';

const PAD = 6; // 강조 상자가 대상보다 조금 크게 그려지는 여백

/** 화면 위에서 대상 요소를 밝게 두고, 옆에 설명 카드를 보여 주는 순서 안내(코치마크). */
export default function GuideTour({ steps, onClose }) {
  const [index, setIndex] = useState(0);
  const [rect, setRect] = useState(null);
  const [pos, setPos] = useState(null);
  const cardRef = useRef(null);
  const step = steps[clampIndex(index, steps.length)];
  const last = index >= steps.length - 1;

  const measure = useCallback(() => {
    const el = document.querySelector(step.target);
    if (!el) return;
    const r = el.getBoundingClientRect();
    setRect({ left: r.left, top: r.top, width: r.width, height: r.height });
  }, [step]);

  // 대상이 화면 밖이면 보이는 곳까지 스크롤하고, 크기·스크롤이 바뀌면 자리를 다시 잰다
  useLayoutEffect(() => {
    const el = document.querySelector(step.target);
    if (!el) return undefined;
    el.scrollIntoView?.({ block: 'nearest', inline: 'nearest' });
    let frame = 0;
    const again = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(measure);
    };
    again();
    window.addEventListener('resize', again);
    window.addEventListener('scroll', again, true);
    const ro = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(again);
    ro?.observe(el);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', again);
      window.removeEventListener('scroll', again, true);
      ro?.disconnect();
    };
  }, [step, measure]);

  useLayoutEffect(() => {
    if (!rect || !cardRef.current) return;
    const size = { width: cardRef.current.offsetWidth, height: cardRef.current.offsetHeight };
    setPos(placeCoach(rect, size, { width: window.innerWidth, height: window.innerHeight }));
  }, [rect, index]);

  useEffect(() => {
    const previous = document.activeElement;
    cardRef.current?.focus();
    return () => previous?.focus?.();
  }, []);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose(); }
      else if (e.key === 'ArrowRight') setIndex((i) => clampIndex(i + 1, steps.length));
      else if (e.key === 'ArrowLeft') setIndex((i) => clampIndex(i - 1, steps.length));
      else if (e.key === 'Tab' && cardRef.current) {
        const items = [...cardRef.current.querySelectorAll('button')];
        if (!items.length) return;
        const firstEl = items[0];
        const lastEl = items[items.length - 1];
        const active = document.activeElement;
        if (e.shiftKey && (active === firstEl || active === cardRef.current)) { e.preventDefault(); lastEl.focus(); }
        else if (!e.shiftKey && active === lastEl) { e.preventDefault(); firstEl.focus(); }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [steps.length, onClose]);

  if (!rect) return null;
  const spot = { left: rect.left - PAD, top: rect.top - PAD, width: rect.width + PAD * 2, height: rect.height + PAD * 2 };

  return createPortal(
    <div className={styles.layer}>
      <div className={styles.blocker} />
      <div className={styles.spot} style={spot} />
      <span className={styles.beacon} style={{ left: spot.left - 7, top: spot.top - 7 }} aria-hidden="true" />
      <section
        ref={cardRef}
        className={styles.card}
        style={{ left: pos?.left ?? -9999, top: pos?.top ?? -9999, visibility: pos ? 'visible' : 'hidden' }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="guide-title"
        tabIndex={-1}
      >
        <Scene key={step.title} name={step.scene} label={step.label} />
        <div className={styles.body}>
          <h2 id="guide-title" className={styles.title}>{step.title}</h2>
          <ul className={styles.bullets}>{step.bullets.map((b) => <li key={b}>{b}</li>)}</ul>
        </div>
        <footer className={styles.foot}>
          <div className={styles.dots} aria-label={`${steps.length}단계 중 ${index + 1}단계`}>
            {steps.map((s, i) => <i key={s.title} className={i === index ? styles.dotOn : ''} />)}
          </div>
          <div className={styles.actions}>
            {last ? null : <button type="button" className={styles.skip} onClick={onClose}>{GUIDE_COPY.skip}</button>}
            <button type="button" className={styles.next} onClick={last ? onClose : () => setIndex(index + 1)}>{last ? GUIDE_COPY.done : GUIDE_COPY.next}</button>
          </div>
        </footer>
      </section>
    </div>,
    document.body,
  );
}
