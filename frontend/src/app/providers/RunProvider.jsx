import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { listRuns } from '../../api/session.js';
import { useAsync } from '../../shared/hooks/useAsync.js';
import { ALL_GU, ROLE, RUN_STATUS } from '../../shared/constants.js';
import { ErrorState } from '../../user/components/States.jsx';
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
  const { data, failed, reload } = useAsync(() => listRuns(), [user?.id]);
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
  if (!run) return null;
  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}

export function useRun() {
  const ctx = useContext(RunContext);
  if (!ctx) throw new Error('RunProvider 안에서만 쓸 수 있습니다.');
  return ctx;
}
