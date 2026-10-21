import { ErrorState, SkeletonRows } from './States.jsx';

/** useAsync 결과를 받아 실패·불러오는 중·내용을 한 곳에서 보인다 (CM-00 12, 13번). 1초 안이면 아무것도 보이지 않는다. */
export default function Loadable({ state, areaName, rows = 6, children }) {
  if (state.failed) return <ErrorState areaName={areaName} onRetry={state.reload} />;
  if (!state.data) return state.showSkeleton ? <SkeletonRows rows={rows} /> : <div style={{ minHeight: 240 }} />;
  return children(state.data);
}
