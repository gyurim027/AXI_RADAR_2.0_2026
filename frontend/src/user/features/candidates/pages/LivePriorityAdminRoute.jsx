import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { backendRequest, priorityBackendEnabled } from '../../../../api/backend.js';
import LivePriorityPage from './LivePriorityPage.jsx';

export default function LivePriorityAdminRoute() {
  const [run, setRun] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!priorityBackendEnabled) {
      setLoading(false);
      return undefined;
    }

    let active = true;

    backendRequest('/api/priority/runs?limit=500')
      .then(data => {
        if (!active) return;
        const runs = Array.isArray(data.runs) ? data.runs : [];
        if (!runs.length) {
          setError('?? ??? ?? ??? ????.');
          return;
        }

        const selected = runs.find(r => Number(r.runId) === 2);
        if (!selected) {
          setError('공식 회차 2를 조회할 수 없어 화면을 열지 않았습니다. 회차 1로 자동 전환하지 않습니다.');
          return;
        }

        setRun({
          id: String(selected.runId),
          actualRunId: selected.runId,
          name: `공식 회차 ${selected.runId}`,
          settingsStatus: selected.settingLinksStatus,
          readOnly: true
        });
      })
      .catch(e => {
        if (active) setError(e.message || String(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, []);

  if (!priorityBackendEnabled) return <Navigate to="/admin" replace />;
  if (loading) return <p role="status">?? ?? ?? ??</p>;
  if (error) return <p role="alert">?? ??: {error}</p>;
  if (!run) return <p>?? ??? ??? ????.</p>;

  return <LivePriorityPage run={run} />;
}
