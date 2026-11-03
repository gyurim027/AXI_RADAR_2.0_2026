import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { listRuns } from '../../api/session.js';
import { useAsync } from '../../shared/hooks/useAsync.js';
import { ALL_GU, ROLE, RUN_STATUS } from '../../shared/constants.js';
import { COMMON } from '../../shared/copy/common.js';
import { EmptyState, ErrorState } from '../../user/components/States.jsx';
import { useAuth } from './AuthProvider.jsx';

const RunContext = createContext(null);

function readSession(key) {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}
function writeSession(key, value) {
  try {
    window.sessionStorage.setItem(key, value);
  } catch {
    /* 저장하지 못해도 화면은 계속 쓴다 */
  }
}

/** 기본값은 '검토 중' 회차, 없으면 가장 최근 '확정' 회차다 (US-00 1-1) */
function defaultRun(runs) {
  return (
    runs.find((r) => r.status === RUN_STATUS.REVIEW) ||
    runs.find((r) => r.status === RUN_STATUS.FINAL) ||
    runs[0] ||
    null
  );
}

export function RunProvider({ children }) {
  const { user } = useAuth();
  const { data, failed, loading, reload } = useAsync(() => listRuns(), [user?.id]);
  const [runId, setRunIdState] = useState(() => readSession('radar.runId'));
  const [guState, setGuState] = useState(() => readSession('radar.gu') || ALL_GU);

  const runs = useMemo(() => data || [], [data]);
  const run = runs.find((r) => r.id === runId) || defaultRun(runs);
  const isCity = user?.role === ROLE.CITY;
  // 도로관리팀은 자기 구만 본다. 시 도로과는 '3개 구 전체'가 기본이다 (US-00 2-1).
  const gu = isCity ? guState : user?.gu || ALL_GU;

  const setRunId = useCallback((id) => {
    setRunIdState(id);
    writeSession('radar.runId', id);
  }, []);
  const setGu = useCallback((value) => {
    setGuState(value);
    writeSession('radar.gu', value);
  }, []);

  const value = useMemo(
    () => ({ runs, run, setRunId, gu, setGu, reloadRuns: reload, ready: !!run }),
    [runs, run, setRunId, gu, setGu, reload],
  );

  if (failed) return <ErrorState areaName="회차 목록" onRetry={reload} />;
  // 서버 응답을 기다리는 동안 '열 수 있는 점검 해가 없다'는 안내가 잠깐 보이지 않게 한다
  if (loading && !data) return <p role="status">회차를 불러오고 있습니다.</p>;
  // E-1 열 수 있는 점검 해가 아직 없다. 빈 화면 대신 이유와 다음 일을 알린다.
  if (!run) return <EmptyState text={COMMON.noCandidates} hint={COMMON.noCandidatesHint} />;
  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}

export function useRun() {
  const ctx = useContext(RunContext);
  if (!ctx) throw new Error('RunProvider 안에서만 쓸 수 있습니다.');
  return ctx;
}
