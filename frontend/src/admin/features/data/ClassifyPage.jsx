import { useState } from 'react';
import { listAdminRuns, listClassify, markClassifyAdmin } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import { useAdminOptional } from '../../AdminProvider.jsx';
import Badge from '../../components/Badge.jsx';
import Button from '../../components/Button.jsx';
import DataTable from '../../components/DataTable.jsx';
import Dialog from '../../components/Dialog.jsx';
import { SelectInput } from '../../components/Field.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import { EmptyState } from '../../components/States.jsx';
import { CLASSIFY } from './copy.js';
import styles from './Data.module.css';
import { reportActionError } from '../../utils/actionError.js';

/** AD-05 분류 검수 (유형 B + E). 사용자 화면 분류 검수와 한 기록으로 남는다. 원문 보기는 확장 단계라 MVP에서는 보이지 않는다. */
export default function ClassifyPage() {
  const ctx = useAdminOptional();
  // 서버 연결 모드에는 위쪽 회차 선택이 없어, 이 화면에서 회차를 고른다 (산정 결과가 있는 회차만)
  const runs = useAsync(() => (ctx ? Promise.resolve([]) : listAdminRuns()), [ctx]);
  const options = (runs.data || []).filter((r) => !r.noResult).sort((a, b) => b.id - a.id);
  const [pickedId, setPickedId] = useState(null);
  const run = ctx ? ctx.run : options.find((r) => r.id === pickedId) || options[0] || null;
  const state = useAsync(() => (run ? listClassify({ runId: run.id }) : Promise.resolve({ items: [], relevance: [], types: [], available: false })), [run?.id]);
  const [fixing, setFixing] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const markOk = async (r) => {
    setBusyId(r.id);
    try {
      await markClassifyAdmin({ id: r.id, result: '맞음' });
      state.reload();
    } catch {
      reportActionError();
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div>
      <PageHeader title={CLASSIFY.title} subtitle={CLASSIFY.subtitle} />
      {!ctx && options.length > 1 ? (
        <div style={{ marginBottom: 16, maxWidth: 280 }}>
          <SelectInput label="회차" value={String(run?.id ?? '')} onChange={(v) => setPickedId(Number(v))} options={options.map((r) => ({ value: String(r.id), label: r.name }))} />
        </div>
      ) : null}
      <Loadable state={state} areaName={CLASSIFY.failedArea} rows={8}>
        {(d) => (
          <>
            <DataTable
              caption={CLASSIFY.title}
              columns={[
                { key: 'summary', header: CLASSIFY.head[0], first: true, width: 300 },
                { key: 'relevance', header: CLASSIFY.head[1], nowrap: true, width: 110 },
                { key: 'label', header: CLASSIFY.head[2], nowrap: true, width: 90, render: (r) => r.label || '-' },
                { key: 'keywords', header: CLASSIFY.head[3], width: 320 },
                { key: 'confidence', header: CLASSIFY.head[4], align: 'right', width: 110, render: (r) => CLASSIFY.confidence(r.confidence) },
                {
                  key: 'action',
                  header: <span className="sr-only">동작</span>,
                  align: 'right',
                  width: 180,
                  render: (r) =>
                    r.done ? (
                      <Badge tone={r.done === '맞음' ? 'success' : 'info'}>{r.done === '맞음' ? CLASSIFY.doneOk : CLASSIFY.doneFix}</Badge>
                    ) : (
                      <span className={styles.rowBtns}>
                        <Button compact variant="secondary" loading={busyId === r.id} onClick={() => markOk(r)} aria-label={`${CLASSIFY.ok}: ${r.summary}`}>
                          {CLASSIFY.okShort}
                        </Button>
                        <Button compact variant="secondary" onClick={() => setFixing(r)} aria-label={`${CLASSIFY.fix}: ${r.summary}`}>
                          {CLASSIFY.fixShort}
                        </Button>
                      </span>
                    ),
                },
              ]}
              rows={d.items}
              getRowKey={(r) => r.id}
              emptyContent={<EmptyState text={ctx ? (run.complaintPeriod ? CLASSIFY.empty : CLASSIFY.emptyNoPeriod) : d.available === false ? CLASSIFY.emptyNoPeriod : CLASSIFY.empty} />}
            />
            {fixing ? (
              <FixDialog
                item={fixing}
                relevance={d.relevance}
                types={d.types}
                onClose={() => setFixing(null)}
                onDone={() => {
                  setFixing(null);
                  state.reload();
                }}
              />
            ) : null}
          </>
        )}
      </Loadable>
    </div>
  );
}

function FixDialog({ item, relevance, types, onClose, onDone }) {
  const [rel, setRel] = useState(item.relevance);
  const [label, setLabel] = useState(item.label || types[0]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const apply = async () => {
    // 바뀐 값이 없으면 보내지 않는다 (ERR-31)
    if (rel === item.relevance && (rel !== '관련' || label === item.label)) return setError(CLASSIFY.errorUnchanged);
    setError('');
    setBusy(true);
    try {
      await markClassifyAdmin({ id: item.id, result: '고침', relevance: rel, label: rel === '관련' ? label : null });
      onDone();
    } catch {
      reportActionError();
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog
      title={CLASSIFY.fixTitle}
      titleId="fix-title"
      subtitle={item.summary}
      onClose={onClose}
      closeLabel={CLASSIFY.fixClose}
      footer={
        <Button variant="primary" loading={busy} onClick={apply}>
          {CLASSIFY.fixApply}
        </Button>
      }
    >
      {error ? <p role="alert">{error}</p> : null}
      <SelectInput label={CLASSIFY.fixRelevance} value={rel} onChange={setRel} options={relevance} />
      <SelectInput label={CLASSIFY.fixType} value={rel === '관련' ? label : ''} onChange={setLabel} options={types} placeholder="-" disabled={rel !== '관련'} help={CLASSIFY.fixTypeHelp} />
    </Dialog>
  );
}
