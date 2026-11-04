import { useState } from 'react';
import { getArticle, getDept, requestDeptApproval, searchLawText } from '../../../api/admin.js';
import { opsBackendEnabled } from '../../../api/backend.js';
import F01PreviewPanel from './F01PreviewPanel.jsx';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import Badge from '../../components/Badge.jsx';
import Button from '../../components/Button.jsx';
import Icon from '../../../user/components/Icon.jsx';
import DataTable from '../../components/DataTable.jsx';
import { TextArea } from '../../components/Field.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Panel, { Banner } from '../../components/Panel.jsx';
import SidePanel from '../../components/SidePanel.jsx';
import { EmptyState } from '../../components/States.jsx';
import { DEPT, REGS } from './copy.js';
import styles from './Standards.module.css';
import { reportActionError } from '../../utils/actionError.js';

const STATUS_TONE = { 확인됨: 'success', '확인 필요': 'warning', '근거 없음': 'neutral' };
const SENT_TONE = { '승인 대기': 'info', 승인: 'success', 반려: 'danger' };

/** AD-11 담당 부서 표 (유형 D): 현재 표는 보기만 하고, AI가 만든 수정안은 근거 원문과 대조한 뒤에만 승인을 요청한다. */
export default function DeptPage() {
  const state = useAsync(() => getDept(), []);
  const [article, setArticle] = useState(null); // 옆 패널에 연 근거 원문
  const [viewed, setViewed] = useState({}); // 원문을 열어 본 수정안
  const [done, setDone] = useState(false);
  const [openId, setOpenId] = useState(null); // 펼친 관할 행(긴 글 전체를 보인다)

  const openArticle = async (draft) => {
    if (draft.statusLabel) {
      // 서버 모드: 승인을 요청한 수정안의 근거(규정 변경 전후와 보유 원문)를 옆에 연다
      setArticle({ title: draft.basis, node: <DraftBasis draft={draft} />, draftId: draft.id });
      return;
    }
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
              <Panel aria-label={DEPT.currentTitle} padded={false}>
                <DataTable
                  caption={DEPT.currentCaption}
                  columns={[
                    { key: 'id', header: DEPT.currentHead[0], first: true, nowrap: true },
                    { key: 'problem', header: DEPT.currentHead[1] },
                    { key: 'dept', header: DEPT.currentHead[2], render: (r) => <span className={styles.clamp}>{r.dept}</span> },
                    { key: 'related', header: DEPT.currentHead[3], render: (r) => <span className={styles.clamp}>{r.related}</span> },
                    { key: 'status', header: DEPT.currentHead[4], nowrap: true, render: (r) => <Badge tone={STATUS_TONE[r.status]}>{r.status}</Badge> },
                    { key: 'basis', header: DEPT.currentHead[5], render: (r) => <span className={styles.clamp}>{r.basis}</span> },
                  ]}
                  rows={d.current}
                  getRowKey={(r) => r.id}
                  expandedKey={openId}
                  onRowClick={(r) => setOpenId(openId === r.id ? null : r.id)}
                  rowLabel={(r) => `${r.id} ${openId === r.id ? '자세히 접기' : '자세히 펼치기'}`}
                  renderExpanded={(r) => (
                    <dl className={styles.fullList}>
                      {[
                        ['building', DEPT.currentHead[2], r.dept],
                        ['link', DEPT.currentHead[3], r.related],
                        ['document', DEPT.currentHead[5], r.basis],
                      ].map(([icon, label, text]) => (
                        <div key={label} className={styles.fullRow}>
                          <dt>
                            <Icon name={icon} size={16} className={styles.fullIcon} />
                            {label}
                          </dt>
                          <dd>{text || '-'}</dd>
                        </div>
                      ))}
                    </dl>
                  )}
                />
              </Panel>
              {opsBackendEnabled ? <F01PreviewPanel /> : null}
              <Panel title={d.sent ? DEPT.sentTitle : DEPT.draftTitle}>
                {done ? <Banner tone="success">{DEPT.requested}</Banner> : null}
                {d.drafts === null ? (
                  <EmptyState text={DEPT.draftsNotConnected} />
                ) : d.drafts.length === 0 ? (
                  <EmptyState text={d.sent ? DEPT.sentEmpty : DEPT.empty} />
                ) : (
                  d.drafts.map((draft) => draft.statusLabel ? (
                    <SentDraftCard key={draft.id} draft={draft} onView={() => openArticle(draft)} />
                  ) : (
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
                {article.node || `${article.text}${article.extra ? `\n\n${article.extra}` : ''}`}
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

/** 서버 모드: 명령으로 올려 시 도로과에 승인을 요청한 수정안. 읽기만 하고, 요청·이유 입력은 없다. */
function SentDraftCard({ draft, onView }) {
  return (
    <div className={styles.draft}>
      <p className={styles.draftText}>
        {DEPT.draftRow(draft.problem, draft.from, draft.to)} <Badge tone={SENT_TONE[draft.statusLabel] || 'neutral'}>{draft.statusLabel}</Badge>
      </p>
      <p className={styles.draftBasis}>{DEPT.draftBasis(draft.basis)}</p>
      {draft.statusLabel === '반려' && draft.reviewComment ? <p className={styles.draftBasis}>{DEPT.returnedReason(draft.reviewComment)}</p> : null}
      <button type="button" className={styles.linkBtn} onClick={onView}>
        {DEPT.viewArticle}
      </button>
    </div>
  );
}

/** 옆 패널: 같은 표 줄에 걸린 규정 변경의 전후 문장 + AI-05가 가진 원문에서 찾은 조문. 원문 찾기는 패널을 열 때 한 번만 한다. */
function DraftBasis({ draft }) {
  const found = useAsync(() => (draft.basisQuery ? searchLawText(draft.basisQuery) : Promise.resolve(null)), [draft.basisQuery]);
  return (
    <div className={styles.stack}>
      <section>
        <h3 className={styles.cmpTitle}>{DEPT.relatedChanges}</h3>
        {draft.changes.length === 0 ? <p>-</p> : draft.changes.map((c) => (
          <div key={c.id}>
            <p className={styles.detected}>{[c.name, c.where, c.date].filter(Boolean).join(' · ')}</p>
            <div className={styles.cmp}>
              <div className={styles.cmpBox}>
                <p className={styles.cmpTitle}>{REGS.beforeTitle}</p>
                {c.before || '-'}
              </div>
              <div className={styles.cmpBox}>
                <p className={styles.cmpTitle}>{REGS.afterTitle}</p>
                {c.after || '-'}
              </div>
            </div>
          </div>
        ))}
      </section>
      <section>
        <h3 className={styles.cmpTitle}>{DEPT.heldText}</h3>
        <Loadable state={found} areaName={DEPT.heldText} rows={2}>
          {(r) => (!r ? <p>-</p> : r.result !== '찾음' || !(r.items || []).length ? <p>{r.result}</p> : r.items.map((it) => (
            <div key={`${it.cite}-${it.para || ''}`} className={styles.cmpBox}>
              <p className={styles.cmpTitle}>{[it.cite, it.status].filter(Boolean).join(' · ')}</p>
              {it.quote}
            </div>
          )))}
        </Loadable>
      </section>
    </div>
  );
}
