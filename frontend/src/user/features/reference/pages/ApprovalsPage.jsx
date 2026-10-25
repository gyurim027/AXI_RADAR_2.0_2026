import { useState } from 'react';
import { applyProposal, decideProposal, listProposals, previewProposal } from '../../../../api/reference.js';
import { approvalErrorMessage } from '../../../../api/approvals.js';
import { i07BackendEnabled } from '../../../../api/backend.js';
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

/** US-10. 실제 API 모드의 승인·반영 상태는 따로 표시한다. 회차·산정값을 만들지 않는다. */
export default function ApprovalsPage() {
  const { user } = useAuth();
  const { data, failed, loading, showSkeleton, reload } = useAsync(() => listProposals(), []);
  const [selectedId, setSelectedId] = useState(null);
  const [rejecting, setRejecting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  const rows = data ?? [];
  const selected = rows.find((p) => p.id === selectedId) || null;
  const preview = useAsync(() => selected ? previewProposal(selected) : Promise.resolve(null), [selectedId, selected?.status]);
  const comparison = !preview.loading && preview.data?.proposalId === selectedId ? preview.data : null;
  const department = selected?.kind === '담당 부서 표';
  const blocked = busy || loading || preview.loading || (department && preview.failed);

  const approve = async () => {
    setBusy(true);
    setNotice(null);
    try {
      const r = selected.pendingApply ? await applyProposal({ id: selected.id }) : await decideProposal({ id: selected.id, approve: true });
      setNotice({ message: r.departmentApplied ? '담당 부서 표 반영을 확인했습니다.' : '승인을 기록했습니다. 산정은 별도로 실행합니다.' });
      setSelectedId(null);
      reload();
    } catch (e) {
      setNotice({ error: true, message: approvalErrorMessage(e) });
      // 승인 뒤 반영 실패로 바뀐 행도 다시 조회한다. 오류를 성공으로 바꾸지 않는다.
      reload();
    } finally {
      setBusy(false);
    }
  };

  const columns = [
    { key: 'name', header: APPROVAL.head[0], render: (p) => APPROVAL.proposalName(p.kind, p.version) },
    { key: 'summary', header: APPROVAL.head[1], render: (p) => <>{p.summary}{p.impact ? <p>{APPROVAL.impact(p.impact.top, p.impact.changed)}</p> : null}{p.pendingApply ? <p>승인됨 · 반영 상태 확인 필요</p> : null}</> },
    { key: 'date', header: APPROVAL.head[2], render: (p) => <span className="num">{p.date}</span> },
  ];

  return (
    <div>
      <PageHeader title={APPROVAL.title} subtitle={i07BackendEnabled ? '제안 내용을 확인하고 승인하거나 돌려보냅니다. 승인 기록과 담당 부서 표 반영 결과는 따로 확인합니다.' : APPROVAL.subtitle} />
      {notice ? <p role={notice.error ? 'alert' : 'status'}>{notice.message}</p> : null}
      <div className={`${styles.split} ${selected ? styles.splitOpen : ''}`}>
        <section className={styles.card} aria-label="제안 목록">
          {failed ? <ErrorState areaName="제안 목록" onRetry={reload} /> : loading && !data ? (
            showSkeleton ? <SkeletonRows rows={4} /> : null
          ) : rows.length === 0 ? <EmptyState text={APPROVAL.empty} /> : (
            <DataTable caption={APPROVAL.title} columns={columns} rows={rows} getRowKey={(p) => p.id} selectedKey={selectedId}
              onRowClick={(p) => { if (!busy) { setSelectedId(p.id); setNotice(null); } }} rowLabel={(p) => `${APPROVAL.proposalName(p.kind, p.version)} 비교 열기`} />
          )}
        </section>
        {selected ? (
          <section className={`${styles.card} ${styles.compare}`} aria-label="제안 비교">
            <h2 className={styles.h2}>{APPROVAL.compareTitle(selected.kind, selected.version)}</h2>
            {preview.loading ? <p role="status">변경 내용을 확인하고 있습니다.</p> : preview.failed ? (
              <p role="alert">{approvalErrorMessage(preview.error)}</p>
            ) : comparison ? (
              <>
                {comparison.changes?.length ? <ul className={styles.changeList}>{comparison.changes.map((c) => (
                  <li key={c.field} className={styles.change}><strong>{APPROVAL.changeRow(c.field, c.from, c.to, c.type)}</strong></li>
                ))}</ul> : <p>{comparison.content || selected.summary}</p>}
                {comparison.impact ? <p>{APPROVAL.impact(comparison.impact.top, comparison.impact.changed)}</p> : null}
              </>
            ) : null}
            {user.readOnly ? null : <div className={styles.btns}>
              {!selected.pendingApply ? <Button variant="soft" disabled={busy || loading} onClick={() => setRejecting(true)}>{APPROVAL.reject}</Button> : null}
              <Button aria-label={selected.pendingApply ? '담당 부서 표 반영 다시 시도' : APPROVAL.approveLabel(selected.kind, selected.version)} disabled={blocked}
                loading={busy} onClick={approve}>{selected.pendingApply ? '반영 다시 시도' : APPROVAL.approve}</Button>
            </div>}
          </section>
        ) : null}
      </div>
      {rejecting && selected ? <RejectModal onClose={() => { if (!busy) setRejecting(false); }} onSend={async (reason) => {
        const r = await decideProposal({ id: selected.id, approve: false, reason });
        if (r.ok) { setRejecting(false); setSelectedId(null); setNotice({ message: '제안을 돌려보냈습니다.' }); reload(); }
        return r;
      }} /> : null}
    </div>
  );
}

function RejectModal({ onClose, onSend }) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const send = async () => {
    if (!reason.trim()) { setError(APPROVAL.rejectReasonError); return; }
    setBusy(true);
    try {
      const r = await onSend(reason.trim());
      if (!r.ok) setError(APPROVAL.rejectReasonError);
    } catch (e) {
      setError(approvalErrorMessage(e));
    } finally { setBusy(false); }
  };
  return (
    <Modal title={APPROVAL.reject} titleId="reject-title" onClose={() => { if (!busy) onClose(); }} closeLabel={APPROVAL.closeLabel}>
      <div className={styles.modalBody}>
        <TextField label={APPROVAL.rejectReasonLabel} value={reason} maxLength={255} onChange={(v) => { setReason(v); setError(''); }} error={error || (reason.length >= 255 ? APPROVAL.reasonTooLong : '')} />
        <div className={styles.btns}><Button onClick={send} loading={busy}>{APPROVAL.rejectSend}</Button></div>
      </div>
    </Modal>
  );
}
