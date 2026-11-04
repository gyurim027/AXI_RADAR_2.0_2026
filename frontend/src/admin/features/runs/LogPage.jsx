import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getExecution, listExecutions, rerunExecution } from '../../../api/admin.js';
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
  const [detail, setDetail] = useState({}); // 서버 줄에는 로그가 없어 펼칠 때 한 건씩 받아 둔다 (id → 한 건)
  const [rerunError, setRerunError] = useState('');
  const state = useAsync(() => listExecutions({ days, status }), [days, status]);
  const { reload } = state;
  const running = (state.data || []).some((e) => e.status === '실행 중');

  // 실행 중인 기록이 있으면 끝났는지 잠깐씩 다시 본다
  useEffect(() => {
    if (!running) return undefined;
    const t = setInterval(() => reload(), 1500);
    return () => clearInterval(t);
  }, [running, reload]);

  const openRow = (state.data || []).find((e) => e.id === openId);
  const needDetail = Boolean(openRow) && !openRow.logs && !detail[openId];
  useEffect(() => {
    if (!needDetail) return undefined;
    let alive = true;
    getExecution({ id: openId })
      .then((d) => alive && setDetail((prev) => ({ ...prev, [openId]: d || { logs: null } })))
      .catch(() => alive && setDetail((prev) => ({ ...prev, [openId]: { logs: null } })));
    return () => {
      alive = false;
    };
  }, [needDetail, openId]);

  const setFilter = (key, value, empty) => {
    const next = new URLSearchParams(params);
    if (value === empty) next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  };

  const rerun = async (e) => {
    setBusy(true);
    setRerunError('');
    try {
      const r = await rerunExecution({ id: e.id });
      if (r?.ok === false) setRerunError(LOG.rerunErrors[r.code] || LOG.rerunErrors.notSupported);
      setDetail((prev) => ({ ...prev, [e.id]: undefined }));
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
            onRowClick={(e) => {
              setRerunError('');
              setOpenId(openId === e.id ? null : e.id);
            }}
            rowLabel={(e) => `${e.name} 로그 ${openId === e.id ? '접기' : '펼치기'}`}
            renderExpanded={(e) => (
              <div className={styles.expanded}>
                <h3 className={styles.h4}>{LOG.logTitle}</h3>
                <pre className={styles.log}>{(e.logs || detail[e.id]?.logs)?.join('\n') ?? (detail[e.id] ? LOG.noLogs : '')}</pre>
                {e.status === '실패' ? (
                  <>
                    <p className={styles.cause} role="alert">
                      {LOG.cause(e.cause)}
                    </p>
                    {rerunError ? (
                      <p className={styles.cause} role="alert">
                        {rerunError}
                      </p>
                    ) : null}
                    {(detail[e.id]?.canRerun ?? e.canRerun) === false ? (
                      <p className={styles.help}>{LOG.cannotRerun}</p>
                    ) : (
                      <>
                        <Button variant="secondary" loading={busy} onClick={() => rerun(e)}>
                          {LOG.rerun}
                        </Button>
                        <p className={styles.help}>{LOG.rerunHelp}</p>
                      </>
                    )}
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
