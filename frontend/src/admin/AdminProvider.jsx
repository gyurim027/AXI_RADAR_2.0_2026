import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { listAdminRuns } from '../api/admin.js';
import { useAsync } from '../shared/hooks/useAsync.js';
import { EmptyState, ErrorState } from './components/States.jsx';

const AdminContext = createContext(null);

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

/** 어드민은 '산정 중'을 포함해 모든 회차를 본다. 기본값은 가장 최근에 만든 회차다 (AD-00 2-1, CM-02 3번). */
export function AdminProvider({ children }) {
  const { data, failed, reload } = useAsync(() => listAdminRuns(), []);
  const [runId, setRunIdState] = useState(() => readSession('radar.admin.runId'));
  const runs = useMemo(() => data || [], [data]);
  const run = runs.find((r) => r.id === runId) || runs[0] || null;

  const setRunId = useCallback((id) => {
    setRunIdState(id);
    writeSession('radar.admin.runId', id);
  }, []);

  const value = useMemo(() => ({ runs, run, setRunId, reloadRuns: reload }), [runs, run, setRunId, reload]);

  if (failed && !data) return <ErrorState areaName="회차 목록" onRetry={reload} />;
  if (!run) return data ? <EmptyState text="아직 만든 회차가 없습니다. 회차를 만들어 주세요." /> : null;
  return <AdminContext.Provider value={value}>{children}</AdminContext.Provider>;
}

/** 서버 연결 모드에는 회차 선택이 없어(AdminProvider가 없다) 없어도 되는 화면이 쓴다. */
export function useAdminOptional() {
  return useContext(AdminContext);
}

export function useAdmin() {
  const ctx = useContext(AdminContext);
  if (!ctx) throw new Error('AdminProvider 안에서만 쓸 수 있습니다.');
  return ctx;
}
