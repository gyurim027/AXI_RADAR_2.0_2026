import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createRun, getNewRunDefaults, getOpenCheck, listAdminRuns, openRun, startCalc } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import { useAdmin } from '../../AdminProvider.jsx';
import Badge, { RUN_TONE } from '../../components/Badge.jsx';
import Button from '../../components/Button.jsx';
import DataTable from '../../components/DataTable.jsx';
import Dialog from '../../components/Dialog.jsx';
import { SelectInput, TextInput } from '../../components/Field.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import { EmptyState } from '../../components/States.jsx';
import { RUNS } from './copy.js';
import styles from './Runs.module.css';

/** AD-06 회차 목록 (유형 B + E): 회차를 만들고, 산정을 시작하고, 검토 중으로 연다. */
export default function RunListPage() {
  const navigate = useNavigate();
  const { reloadRuns } = useAdmin();
  const state = useAsync(() => listAdminRuns(), []);
  const [creating, setCreating] = useState(false);
  const [opening, setOpening] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState('');

  const start = async (r) => {
    setBusyId(r.id);
    setError('');
    try {
      await startCalc({ runId: r.id });
      reloadRuns();
      navigate('/admin/runs/log'); // '산정 시작하기'는 실행 기록으로 간다
    } catch {
      setError(RUNS.startFailed);
      setBusyId(null);
    }
  };

  const columns = [
    { key: 'name', header: RUNS.head[0], first: true, nowrap: true },
    { key: 'kindLabel', header: RUNS.head[1], nowrap: true },
    { key: 'status', header: RUNS.head[2], nowrap: true, render: (r) => <Badge tone={RUN_TONE[r.status]}>{r.status}</Badge> },
    { key: 'version', header: RUNS.head[3], nowrap: true },
    { key: 'created', header: RUNS.head[4], nowrap: true },
    { key: 'review', header: RUNS.head[5], nowrap: true, render: (r) => r.review || '-' },
    {
      key: 'action',
      header: <span className="sr-only">동작</span>,
      align: 'right',
      render: (r) => {
        if (r.status !== '산정 중') return null;
        if (r.calcDone) {
          return (
            <Button compact variant="secondary" onClick={() => setOpening(r)} aria-label={`${r.name} ${RUNS.openRun}`}>
              {RUNS.openRun}
            </Button>
          );
        }
        if (!r.ran) {
          return (
            <Button compact variant="secondary" loading={busyId === r.id} onClick={() => start(r)} aria-label={`${r.name} ${RUNS.startCalc}`}>
              {RUNS.startCalc}
            </Button>
          );
        }
        return null;
      },
    },
  ];

  return (
    <div>
      <PageHeader title={RUNS.title} subtitle={RUNS.subtitle}>
        <Button variant="primary" onClick={() => setCreating(true)}>
          {RUNS.create}
        </Button>
      </PageHeader>
      {error ? (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      ) : null}
      <Loadable state={state} areaName={RUNS.failedArea} rows={5}>
        {(rows) => (
          <DataTable caption={RUNS.caption} columns={columns} rows={rows} getRowKey={(r) => r.id} emptyContent={<EmptyState text={RUNS.empty} />} />
        )}
      </Loadable>
      {creating ? (
        <NewRunDialog
          onClose={() => setCreating(false)}
          onCreated={() => {
            setCreating(false);
            state.reload();
            reloadRuns();
          }}
        />
      ) : null}
      {opening ? (
        <OpenDialog
          run={opening}
          onClose={() => setOpening(null)}
          onOpened={() => {
            setOpening(null);
            state.reload();
            reloadRuns();
          }}
        />
      ) : null}
    </div>
  );
}

/** 1-2 새 회차 창: 종류를 고르면 이름을 자동으로 채운다. 고칠 수 있다. */
function NewRunDialog({ onClose, onCreated }) {
  const defaults = useAsync(() => getNewRunDefaults(), []);
  const year = defaults.data?.year ?? new Date().getFullYear() + 1;
  const [kind, setKind] = useState('연간');
  const [name, setName] = useState('');
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const shown = touched ? name : RUNS.suggest(year, kind);

  const submit = async () => {
    setBusy(true);
    try {
      const r = await createRun({ kind, name: shown });
      if (r.ok) onCreated();
      else if (r.code === 'duplicate') setError(RUNS.nameDuplicate);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      title={RUNS.newTitle}
      titleId="new-run-title"
      onClose={onClose}
      closeLabel={RUNS.newClose}
      footer={
        <Button variant="primary" loading={busy} disabled={!shown.trim()} onClick={submit}>
          {RUNS.create}
        </Button>
      }
    >
      <SelectInput
        label={RUNS.kind}
        value={kind}
        onChange={(v) => {
          setKind(v);
          setError('');
        }}
        options={RUNS.kinds}
      />
      <TextInput
        label={RUNS.name}
        value={shown}
        onChange={(v) => {
          setName(v);
          setTouched(true);
          setError('');
        }}
        help={RUNS.nameHelp(RUNS.suggest(year, '연간'), RUNS.suggest(year, '반기 참고'))}
        error={error}
      />
    </Dialog>
  );
}

/** 2-1 회차 열기 확인 창: 열기 전에 빠진 자료와 미평가 분야를 본다. 빠진 자료가 있어도 열 수는 있다. */
function OpenDialog({ run, onClose, onOpened }) {
  const navigate = useNavigate();
  const state = useAsync(() => getOpenCheck({ runId: run.id }), [run.id]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const open = async () => {
    setBusy(true);
    try {
      const r = await openRun({ runId: run.id });
      if (r.ok) onOpened();
      else setError(RUNS.notFinished);
    } finally {
      setBusy(false);
    }
  };
  const data = state.data;
  return (
    <Dialog
      title={RUNS.openTitle(run.name)}
      titleId="open-run-title"
      subtitle={RUNS.openSub}
      size="md"
      onClose={onClose}
      closeLabel={RUNS.openClose}
      footer={
        <>
          {data && data.missing.length > 0 ? (
            <Button variant="secondary" onClick={() => navigate('/admin/data/list?freshness=빠짐')}>
              {RUNS.goMissing}
            </Button>
          ) : null}
          <Button variant="primary" loading={busy} onClick={open} disabled={!data}>
            {RUNS.openRun}
          </Button>
        </>
      }
    >
      <Loadable state={state} areaName="빠진 자료" rows={3}>
        {(d) => (
          <>
            {d.missing.length > 0 ? (
              <section>
                <h3 className={styles.h3}>{RUNS.missingTitle}</h3>
                <ul className={styles.list}>
                  {d.missing.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              </section>
            ) : null}
            <section>
              <h3 className={styles.h3}>{RUNS.unratedTitle}</h3>
              <ul className={styles.list}>
                {d.unrated.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            </section>
            {d.run.kind === 'ref' ? <p className={styles.note}>{RUNS.refNote}</p> : null}
          </>
        )}
      </Loadable>
      {error ? (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      ) : null}
    </Dialog>
  );
}
