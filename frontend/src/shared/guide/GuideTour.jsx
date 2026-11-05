import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { GUIDE_COPY } from './guideConfig.js';
import { clampIndex, placeCoach } from './guideLogic.js';
import Scene from './scenes.jsx';
import styles from './GuideTour.module.css';

const PAD = 6; // 강조 상자가 대상보다 조금 크게 그려지는 여백

/**
 * 화면 위에서 대상 요소를 밝게 두고, 옆에 설명 카드를 보여 주는 순서 안내(코치마크).
 * 마지막 카드가 `다음은 ○○` 이동 카드(kind: 'next')나 `핵심 경로를 마쳤습니다`(kind: 'end')일 수 있다.
 * 단계 점(페이지 표시)을 누르면 그 단계로 이동하고, `다음은 ○○` 카드의 `다음`은 다음 화면으로 이동(onGo)한다.
 */
export default function GuideTour({ steps, onClose, onGo }) {
  const [index, setIndex] = useState(0);
  const [rect, setRect] = useState(null);
  const [pos, setPos] = useState(null);
  const cardRef = useRef(null);
  const step = steps[clampIndex(index, steps.length)];
  const last = index >= steps.length - 1;
  const isNext = step.kind === 'next';

  const measure = useCallback(() => {
    const el = step.target ? document.querySelector(step.target) : null;
    if (!el) { setRect(null); return; }
    const r = el.getBoundingClientRect();
    setRect({ left: r.left, top: r.top, width: r.width, height: r.height });
  }, [step]);

  // 대상이 화면 밖이면 보이는 곳까지 스크롤하고, 크기·스크롤이 바뀌면 자리를 다시 잰다. 대상이 없으면 카드를 가운데에 둔다.
  useLayoutEffect(() => {
    const el = step.target ? document.querySelector(step.target) : null;
    el?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' });
    let frame = 0;
    const again = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(measure);
    };
    again();
    window.addEventListener('resize', again);
    window.addEventListener('scroll', again, true);
    const ro = el && typeof ResizeObserver !== 'undefined' ? new ResizeObserver(again) : null;
    ro?.observe(el);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', again);
      window.removeEventListener('scroll', again, true);
      ro?.disconnect();
    };
  }, [step, measure]);

  useLayoutEffect(() => {
    if (!cardRef.current) return;
    const size = { width: cardRef.current.offsetWidth, height: cardRef.current.offsetHeight };
    const viewport = { width: window.innerWidth, height: window.innerHeight };
    setPos(rect ? placeCoach(rect, size, viewport) : { side: 'center', left: Math.max(12, (viewport.width - size.width) / 2), top: Math.max(12, (viewport.height - size.height) / 2) });
  }, [rect, index]);

  useEffect(() => {
    const previous = document.activeElement;
    cardRef.current?.focus();
    return () => previous?.focus?.();
  }, []);

  const goNext = useCallback(() => {
    if (isNext) onGo?.(step.to);
    else if (last) onClose();
    else setIndex((i) => clampIndex(i + 1, steps.length));
  }, [isNext, last, onClose, onGo, step, steps.length]);

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

  const spot = rect ? { left: rect.left - PAD, top: rect.top - PAD, width: rect.width + PAD * 2, height: rect.height + PAD * 2 } : null;
  // 이동 카드도 다른 카드와 같은 버튼 이름을 쓴다: `건너뛰기`, `다음`(마지막 카드만 `완료`)
  const primary = last && !isNext ? GUIDE_COPY.done : GUIDE_COPY.next;
  const secondary = last && !isNext ? null : GUIDE_COPY.skip;

  return createPortal(
    <div className={styles.layer}>
      <div className={`${styles.blocker} ${spot ? '' : styles.dim}`} />
      {spot ? <div className={styles.spot} style={spot} /> : null}
      {spot ? <span className={styles.beacon} style={{ left: spot.left - 7, top: spot.top - 7 }} aria-hidden="true" /> : null}
      <section
        ref={cardRef}
        className={styles.card}
        style={{ left: pos?.left ?? -9999, top: pos?.top ?? -9999, visibility: pos ? 'visible' : 'hidden' }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="guide-title"
        tabIndex={-1}
      >
        <div className={styles.sceneWrap}>
          <Scene key={step.title} name={step.scene} label={step.label} />
        </div>
        <div className={styles.body}>
          <h2 id="guide-title" className={styles.title}>{step.title}</h2>
          <ul className={styles.bullets}>{step.bullets.map((b) => <li key={b}>{b}</li>)}</ul>
        </div>
        <footer className={styles.foot}>
          <div className={styles.dots} role="group" aria-label={GUIDE_COPY.pagesLabel}>
            {steps.map((s, i) => (
              <button key={s.title} type="button" className={`${styles.dot} ${i === index ? styles.dotOn : ''}`} aria-label={`${i + 1}단계 안내 보기`} aria-current={i === index ? 'step' : undefined} onClick={() => setIndex(i)} />
            ))}
          </div>
          <div className={styles.actions}>
            {secondary ? <button type="button" className={styles.skip} onClick={onClose}>{secondary}</button> : null}
            <button type="button" className={styles.next} onClick={goNext}>{primary}</button>
          </div>
        </footer>
      </section>
    </div>,
    document.body,
  );
}
