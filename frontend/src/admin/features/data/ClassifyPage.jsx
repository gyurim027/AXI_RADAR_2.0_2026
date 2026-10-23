import { useState } from 'react';
import { listClassify, markClassifyAdmin } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import { useAdmin } from '../../AdminProvider.jsx';
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
  const { run } = useAdmin();
  const state = useAsync(() => listClassify({ runId: run.id }), [run.id]);
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
      <Loadable state={state} areaName={CLASSIFY.failedArea} rows={8}>
        {(d) => (
          <>
            <DataTable
              caption={CLASSIFY.title}
              columns={[
                { key: 'summary', header: CLASSIFY.head[0], first: true },
                { key: 'relevance', header: CLASSIFY.head[1], nowrap: true },
                { key: 'label', header: CLASSIFY.head[2] },
                { key: 'keywords', header: CLASSIFY.head[3] },
                { key: 'confidence', header: CLASSIFY.head[4], align: 'right', render: (r) => CLASSIFY.confidence(r.confidence) },
                {
                  key: 'action',
                  header: <span className="sr-only">동작</span>,
                  align: 'right',
                  render: (r) =>
                    r.done ? (
                      <Badge tone={r.done === '맞음' ? 'success' : 'info'}>{r.done === '맞음' ? CLASSIFY.doneOk : CLASSIFY.doneFix}</Badge>
                    ) : (
                      <span className={styles.rowBtns}>
                        <Button compact variant="secondary" loading={busyId === r.id} onClick={() => markOk(r)} aria-label={`${CLASSIFY.ok}: ${r.summary}`}>
                          {CLASSIFY.ok}
                        </Button>
                        <Button compact variant="secondary" onClick={() => setFixing(r)} aria-label={`${CLASSIFY.fix}: ${r.summary}`}>
                          {CLASSIFY.fix}
                        </Button>
                      </span>
                    ),
                },
              ]}
              rows={d.items}
              getRowKey={(r) => r.id}
              emptyContent={<EmptyState text={CLASSIFY.empty} />}
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
  const [label, setLabel] = useState(item.label);
  const [busy, setBusy] = useState(false);
  const apply = async () => {
    setBusy(true);
    try {
      await markClassifyAdmin({ id: item.id, result: '고침', relevance: rel, label });
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
      <SelectInput label={CLASSIFY.fixRelevance} value={rel} onChange={setRel} options={relevance} />
      <SelectInput label={CLASSIFY.fixType} value={label} onChange={setLabel} options={types} />
    </Dialog>
  );
}
