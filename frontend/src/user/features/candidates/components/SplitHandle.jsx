import { useRef } from 'react';
import { SPLIT } from '../copy.js';
import { DEFAULT_STATE, nextByKey, resolveRatio } from '../split.js';
import styles from './SplitHandle.module.css';

/**
 * 표와 지도 사이의 분할 막대. 끌거나 방향키로 비율을 바꾼다. 한쪽 한도를 넘겨 끌면 그쪽이 접히고,
 * 접힌 쪽은 막대를 반대로 끌거나 두 번 눌러 되돌린다. 막대는 윈도 스플리터(separator) 모양이다.
 */
export default function SplitHandle({ state, onChange, onDragState, containerRef }) {
  const drag = useRef(null);
  const widthOf = () => containerRef.current?.getBoundingClientRect().width || 0;
  const pct = Math.round((state.mode === 'table' ? 1 : state.mode === 'map' ? 0 : state.ratio) * 100);

  const onPointerDown = (e) => {
    if (e.button !== 0 && e.pointerType === 'mouse') return;
    const box = containerRef.current?.getBoundingClientRect();
    if (!box) return;
    drag.current = { left: box.left, width: box.width };
    e.currentTarget.setPointerCapture(e.pointerId);
    onDragState(true);
  };
  const onPointerMove = (e) => {
    const d = drag.current;
    if (!d) return;
    onChange(resolveRatio((e.clientX - d.left) / d.width, d.width), { animate: false });
  };
  const end = (e) => {
    if (!drag.current) return;
    drag.current = null;
    e.currentTarget.releasePointerCapture?.(e.pointerId);
    onDragState(false);
  };
  const onKeyDown = (e) => {
    const next = nextByKey(state, e.key, widthOf());
    if (!next) return;
    e.preventDefault();
    onChange(next, { animate: true });
  };

  return (
    <div className={styles.wrap} data-mode={state.mode}>
      <div
        className={styles.bar}
        role="separator"
        aria-orientation="vertical"
        aria-label={SPLIT.label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-valuetext={SPLIT.valueText(state.mode, pct)}
        aria-keyshortcuts="ArrowLeft ArrowRight Home End Enter"
        tabIndex={0}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={end}
        onPointerCancel={end}
        onKeyDown={onKeyDown}
        onDoubleClick={() => onChange(DEFAULT_STATE, { animate: true })}
      />
    </div>
  );
}
