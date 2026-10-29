import { useState } from 'react';
import { getArticle, getDept, requestDeptApproval } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import Badge from '../../components/Badge.jsx';
import Button from '../../components/Button.jsx';
import DataTable from '../../components/DataTable.jsx';
import { TextArea } from '../../components/Field.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Panel, { Banner } from '../../components/Panel.jsx';
import SidePanel from '../../components/SidePanel.jsx';
import { EmptyState } from '../../components/States.jsx';
import { DEPT } from './copy.js';
import styles from './Standards.module.css';
import { reportActionError } from '../../utils/actionError.js';

const STATUS_TONE = { 확인됨: 'success', '확인 필요': 'warning', '근거 없음': 'neutral' };

/** AD-11 담당 부서 표 (유형 D): 현재 표는 보기만 하고, AI가 만든 수정안은 근거 원문과 대조한 뒤에만 승인을 요청한다. */
export default function DeptPage() {
  const state = useAsync(() => getDept(), []);
  const [article, setArticle] = useState(null); // 옆 패널에 연 근거 원문
  const [viewed, setViewed] = useState({}); // 원문을 열어 본 수정안
  const [done, setDone] = useState(false);

  const openArticle = async (draft) => {
    const a = await getArticle({ draftId: draft.id });
    setArticle({ ...a, draftId: draft.id });
    setViewed((v) => ({ ...v, [draft.id]: true }));
  };

  return (
    <div>
      <PageHeader title={DEPT.title} subtitle={DEPT.subtitle} />
      <Loadable state={state} areaName={DEPT.failedArea} rows={6}>
        {(d) => (
          <div className={styles.row}>
            <div className={`${styles.stack} ${styles.main}`}>
              <Panel title={DEPT.currentTitle} padded={false}>
                <DataTable
                  caption={DEPT.currentCaption}
                  columns={[
                    { key: 'id', header: DEPT.currentHead[0], first: true, nowrap: true },
                    { key: 'problem', header: DEPT.currentHead[1] },
                    { key: 'dept', header: DEPT.currentHead[2] },
                    { key: 'related', header: DEPT.currentHead[3] },
                    { key: 'status', header: DEPT.currentHead[4], nowrap: true, render: (r) => <Badge tone={STATUS_TONE[r.status]}>{r.status}</Badge> },
                    { key: 'basis', header: DEPT.currentHead[5] },
                  ]}
                  rows={d.current}
                  getRowKey={(r) => r.id}
                />
              </Panel>
              <Panel title={DEPT.draftTitle}>
                {done ? <Banner tone="success">{DEPT.requested}</Banner> : null}
                {d.drafts === null ? (
                  <EmptyState text={DEPT.draftsNotConnected} />
                ) : d.drafts.length === 0 ? (
                  <EmptyState text={DEPT.empty} />
                ) : (
                  d.drafts.map((draft) => (
                    <DraftCard
                      key={draft.id}
                      draft={draft}
                      viewed={!!viewed[draft.id]}
                      onView={() => openArticle(draft)}
                      onRequested={() => {
                        setDone(true);
                        setArticle(null);
                        state.reload();
                      }}
                    />
                  ))
                )}
                {d.drafts === null ? null : <p className={styles.note}>{DEPT.note}</p>}
              </Panel>
            </div>
            {article ? (
              <SidePanel title={article.title} titleId="article-title" onClose={() => setArticle(null)} closeLabel={DEPT.articleClose}>
                {article.text}
                {article.extra ? `\n\n${article.extra}` : ''}
              </SidePanel>
            ) : null}
          </div>
        )}
      </Loadable>
    </div>
  );
}

function DraftCard({ draft, viewed, onView, onRequested }) {
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const request = async () => {
    setBusy(true);
    try {
      const r = await requestDeptApproval({ draftId: draft.id, reason });
      if (r.ok) onRequested();
    } catch {
      reportActionError();
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className={styles.draft}>
      <p className={styles.draftText}>{DEPT.draftRow(draft.problem, draft.from, draft.to)}</p>
      <p className={styles.draftBasis}>{DEPT.draftBasis(draft.basis)}</p>
      <button type="button" className={styles.linkBtn} onClick={onView}>
        {DEPT.viewArticle}
      </button>
      <TextArea label={DEPT.reasonLabel} value={reason} onChange={setReason} rows={2} />
      {/* 운영자가 원문과 대조한 뒤에만 요청할 수 있다 */}
      <div>
        <Button variant="primary" loading={busy} disabled={!viewed || !reason.trim()} onClick={request}>
          {DEPT.request}
        </Button>
      </div>
    </div>
  );
}
