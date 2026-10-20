import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { listExecutions, rerunExecution } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import Badge, { EXEC_TONE } from '../../components/Badge.jsx';
import Button from '../../components/Button.jsx';
import DataTable from '../../components/DataTable.jsx';
import { SelectInput } from '../../components/Field.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import { EmptyState } from '../../components/States.jsx';
import Toolbar from '../../components/Toolbar.jsx';
import { LOG } from './copy.js';
import styles from './Runs.module.css';
import { reportActionError } from '../../utils/actionError.js';

/** AD-07 실행 기록 (유형 B): 최신 순. 행을 누르면 아래에 로그가 펼쳐진다. 긴 표는 안에서 스크롤하고 머리 줄은 고정한다. */
export default function LogPage() {
  const [params, setParams] = useSearchParams();
  const days = params.get('days') || '30';
  const status = params.get('status') || '전체';
  const [openId, setOpenId] = useState(null);
  const [busy, setBusy] = useState(false);
  const state = useAsync(() => listExecutions({ days, status }), [days, status]);
  const { reload } = state;
  const running = (state.data || []).some((e) => e.status === '실행 중');

  // 실행 중인 기록이 있으면 끝났는지 잠깐씩 다시 본다
  useEffect(() => {
    if (!running) return undefined;
    const t = setInterval(() => reload(), 1500);
    return () => clearInterval(t);
  }, [running, reload]);

  const setFilter = (key, value, empty) => {
    const next = new URLSearchParams(params);
    if (value === empty) next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  };

  const rerun = async (e) => {
    setBusy(true);
    try {
      await rerunExecution({ id: e.id });
      state.reload();
    } catch {
      reportActionError();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader title={LOG.title} subtitle={LOG.subtitle} />
      <Toolbar>
        <SelectInput label={LOG.period} value={days} onChange={(v) => setFilter('days', v, '30')} options={LOG.periods} />
        <SelectInput label={LOG.status} value={status} onChange={(v) => setFilter('status', v, '전체')} options={LOG.statuses} />
      </Toolbar>
      <Loadable state={state} areaName={LOG.failedArea} rows={8}>
        {(rows) => (
          <DataTable
            caption={LOG.caption}
            compact
            maxHeight={640}
            columns={[
              { key: 'name', header: LOG.head[0], first: true },
              { key: 'kind', header: LOG.head[1], nowrap: true },
              { key: 'status', header: LOG.head[2], nowrap: true, render: (e) => <Badge tone={EXEC_TONE[e.status]}>{e.status}</Badge> },
              { key: 'atLabel', header: LOG.head[3], nowrap: true },
              { key: 'minutes', header: LOG.head[4], align: 'right', nowrap: true, render: (e) => LOG.minutes(e.minutes) },
            ]}
            rows={rows}
            getRowKey={(e) => e.id}
            expandedKey={openId}
            onRowClick={(e) => setOpenId(openId === e.id ? null : e.id)}
            rowLabel={(e) => `${e.name} 로그 ${openId === e.id ? '접기' : '펼치기'}`}
            renderExpanded={(e) => (
              <div className={styles.expanded}>
                <h3 className={styles.h4}>{LOG.logTitle}</h3>
                <pre className={styles.log}>{e.logs.join('\n')}</pre>
                {e.status === '실패' ? (
                  <>
                    <p className={styles.cause} role="alert">
                      {LOG.cause(e.cause)}
                    </p>
                    <Button variant="secondary" loading={busy} onClick={() => rerun(e)}>
                      {LOG.rerun}
                    </Button>
                    <p className={styles.help}>{LOG.rerunHelp}</p>
                  </>
                ) : null}
              </div>
            )}
            emptyContent={<EmptyState text={LOG.empty} />}
          />
        )}
      </Loadable>
    </div>
  );
}
