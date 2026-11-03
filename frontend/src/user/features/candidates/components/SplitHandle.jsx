import { useRef } from 'react';
import Icon from '../../../components/Icon.jsx';
import { SPLIT } from '../copy.js';
import { DEFAULT_STATE, nextByKey, resolveRatio } from '../split.js';
import styles from './SplitHandle.module.css';

/**
 * 표와 지도 사이의 분할 막대. 끌거나 방향키로 비율을 바꾸고, 단추로 한쪽만 볼 수 있다.
 * 막대는 윈도 스플리터(separator) 모양이고 단추는 막대 밖 형제다.
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

  const modes = [
    { id: 'map', label: SPLIT.mapOnly, icon: 'chevronLeft' },
    { id: 'split', label: SPLIT.reset, text: SPLIT.resetShort },
    { id: 'table', label: SPLIT.tableOnly, icon: 'chevronRight' },
  ];

  return (
    <div className={styles.wrap}>
      <div
        className={styles.bar}
        role="separator"
        aria-orientation="vertical"
        aria-label={SPLIT.label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-valuetext={SPLIT.valueText(state.mode, pct)}
        tabIndex={0}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={end}
        onPointerCancel={end}
        onKeyDown={onKeyDown}
        onDoubleClick={() => onChange(DEFAULT_STATE, { animate: true })}
      />
      <div className={styles.btns} role="group" aria-label={SPLIT.group}>
        {modes.map((m) => (
          <button
            key={m.id}
            type="button"
            className={`${styles.btn} ${state.mode === m.id ? styles.on : ''}`}
            aria-pressed={state.mode === m.id}
            aria-label={m.label}
            title={m.label}
            onClick={() => onChange(m.id === 'split' ? DEFAULT_STATE : { mode: m.id, ratio: state.ratio }, { animate: true })}
          >
            {m.icon ? <Icon name={m.icon} size={16} /> : <span aria-hidden="true">{m.text}</span>}
          </button>
        ))}
      </div>
    </div>
  );
}
