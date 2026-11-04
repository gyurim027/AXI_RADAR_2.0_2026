import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * 비동기 데이터 불러오기.
 * - 1초가 넘게 걸릴 때만 showSkeleton이 true가 된다 (CM-00 13번: 1초 안이면 아무것도 보이지 않는다).
 * - 다시 불러올 때는 이전 데이터를 남겨 화면이 흔들리지 않게 한다.
 * - deps가 바뀌거나 reload()를 부르면 새로 불러온다.
 */
export function useAsync(fn, deps, { skeletonAfterMs = 1000 } = {}) {
  const [tick, setTick] = useState(0);
  const key = `${tick}:${deps.map(String).join('|')}`;
  const [result, setResult] = useState({ key: null, data: null, error: null });
  const [slowKey, setSlowKey] = useState(null);
  const fnRef = useRef(fn);

  useEffect(() => {
    fnRef.current = fn;
  });

  useEffect(() => {
    let alive = true;
    const timer = setTimeout(() => alive && setSlowKey(key), skeletonAfterMs);
    fnRef
      .current()
      .then((data) => alive && setResult({ key, data, error: null }))
      .catch((error) => alive && setResult((prev) => ({ key, data: prev.data, error })));
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [key, skeletonAfterMs]);

  const loading = result.key !== key;
  const failed = !loading && result.error != null;
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return {
    data: result.data,
    error: failed ? result.error : null,
    status: loading ? 'loading' : failed ? 'error' : 'ok',
    loading,
    failed,
    showSkeleton: loading && slowKey === key,
    reload,
  };
}
