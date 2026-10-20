import { useState } from 'react';
import { decideProposal, listProposals } from '../../../../api/reference.js';
import { useAuth } from '../../../../app/providers/AuthProvider.jsx';
import { useAsync } from '../../../../shared/hooks/useAsync.js';
import Button from '../../../components/Button.jsx';
import DataTable from '../../../components/DataTable.jsx';
import Modal from '../../../components/Modal.jsx';
import PageHeader from '../../../components/PageHeader.jsx';
import { TextField } from '../../../components/FormControls.jsx';
import { EmptyState, ErrorState, SkeletonRows } from '../../../components/States.jsx';
import { APPROVAL } from '../copy.js';
import styles from './Reference.module.css';

/** US-10 승인 대기 (시 도로과만). 행을 누르면 오른쪽에 비교가 열린다. 시 도로과만 승인한다. */
export default function ApprovalsPage() {
  const { user } = useAuth();
  const { data, failed, loading, showSkeleton, reload } = useAsync(() => listProposals(), []);
  const [selectedId, setSelectedId] = useState(null);
  const [rejecting, setRejecting] = useState(false);
  const [busy, setBusy] = useState(false);
  const rows = data ?? []; // 오래된 순
  const selected = rows.find((p) => p.id === selectedId) || null;

  const approve = async () => {
    setBusy(true);
    try {
      await decideProposal({ id: selected.id, approve: true }); // 새 버전은 다음 산정부터 쓴다
      setSelectedId(null);
      reload();
    } finally {
      setBusy(false);
    }
  };

  const columns = [
    { key: 'name', header: APPROVAL.head[0], render: (p) => APPROVAL.proposalName(p.kind, p.version) },
    { key: 'summary', header: APPROVAL.head[1], render: (p) => p.summary },
    { key: 'date', header: APPROVAL.head[2], render: (p) => <span className="num">{p.date}</span> },
  ];

  return (
    <div>
      <PageHeader title={APPROVAL.title} subtitle={APPROVAL.subtitle} />
      <div className={`${styles.split} ${selected ? styles.splitOpen : ''}`}>
        <section className={styles.card} aria-label="제안 목록">
          {failed ? (
            <ErrorState areaName="제안 목록" onRetry={reload} />
          ) : loading && !data ? (
            showSkeleton ? <SkeletonRows rows={4} /> : null
          ) : rows.length === 0 ? (
            <EmptyState text={APPROVAL.empty} />
          ) : (
            <DataTable caption={APPROVAL.title} columns={columns} rows={rows} getRowKey={(p) => p.id} selectedKey={selectedId} onRowClick={(p) => setSelectedId(p.id)} rowLabel={(p) => `${APPROVAL.proposalName(p.kind, p.version)} 비교 열기`} />
          )}
        </section>

        {selected ? (
          <section className={`${styles.card} ${styles.compare}`} aria-label="제안 비교">
            <h2 className={styles.h2}>{APPROVAL.compareTitle(selected.kind, selected.version)}</h2>
            <ul className={styles.changeList}>
              {selected.changes.map((c) => (
                <li key={c.field} className={styles.change}>
                  {/* 바뀐 칸만 진하게 보인다 */}
                  <strong>{APPROVAL.changeRow(c.field, c.from, c.to, c.type)}</strong>
                </li>
              ))}
            </ul>
            {selected.impact ? <p>{APPROVAL.impact(selected.impact.top, selected.impact.changed)}</p> : null}
            {user.readOnly ? null : (
              <div className={styles.btns}>
                <Button variant="soft" onClick={() => setRejecting(true)}>
                  {APPROVAL.reject}
                </Button>
                <Button aria-label={APPROVAL.approveLabel(selected.kind, selected.version)} loading={busy} onClick={approve}>
                  {APPROVAL.approve}
                </Button>
              </div>
            )}
          </section>
        ) : null}
      </div>

      {rejecting && selected ? (
        <RejectModal
          onClose={() => setRejecting(false)}
          onSend={async (reason) => {
            const r = await decideProposal({ id: selected.id, approve: false, reason });
            if (r.ok) {
              setRejecting(false);
              setSelectedId(null);
              reload();
            }
            return r;
          }}
        />
      ) : null}
    </div>
  );
}

/** 돌려보내는 사유 입력 창. 사유는 필수다. */
function RejectModal({ onClose, onSend }) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    try {
      const r = await onSend(reason);
      if (!r.ok) setError(APPROVAL.rejectReasonError);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal title={APPROVAL.reject} titleId="reject-title" onClose={onClose} closeLabel={APPROVAL.closeLabel}>
      <div className={styles.modalBody}>
        <TextField
          label={APPROVAL.rejectReasonLabel}
          value={reason}
          onChange={(v) => {
            setReason(v);
            setError('');
          }}
          error={error}
        />
        <div className={styles.btns}>
          <Button onClick={send} loading={busy}>
            {APPROVAL.rejectSend}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
