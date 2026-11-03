import { useCallback, useEffect, useState } from 'react';
import { readStoredState, trackFractions, writeStoredState } from './split.js';

const WIDE = '(min-width: 1100px)';

/** 표·지도 분할의 상태. 1100px 미만에서는 위아래로 쌓이므로 접기를 쓰지 않는다. */
export default function useSplit() {
  const [state, setState] = useState(readStoredState);
  const [dragging, setDragging] = useState(false);
  const [animating, setAnimating] = useState(false);
  const [wide, setWide] = useState(() => window.matchMedia(WIDE).matches);

  useEffect(() => {
    const mq = window.matchMedia(WIDE);
    const on = () => setWide(mq.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);

  useEffect(() => {
    if (!animating) return undefined;
    const t = setTimeout(() => setAnimating(false), 260);
    return () => clearTimeout(t);
  }, [animating]);

  // 끄는 동안에는 저장하지 않고, 놓은 뒤 한 번만 저장한다.
  useEffect(() => {
    if (!dragging) writeStoredState(state);
  }, [state, dragging]);

  const change = useCallback((next, { animate = false } = {}) => {
    setAnimating(animate);
    setState((prev) => (prev.mode === next.mode && prev.ratio === next.ratio ? prev : { mode: next.mode, ratio: next.ratio }));
  }, []);

  const f = trackFractions(state);
  return {
    state,
    wide,
    change,
    setDragging,
    animating,
    dragging,
    style: wide ? { '--split-left': `${f.left}fr`, '--split-right': `${f.right}fr` } : undefined,
    tableHidden: wide && state.mode === 'map',
    mapHidden: wide && state.mode === 'table',
  };
}
