import { useState } from 'react';
import { getActionTable, getDraftArticle, recordAdminDownload, saveActionDraft, saveActionRow } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import { downloadCsv } from '../../utils/downloadCsv.js';
import Badge from '../../components/Badge.jsx';
import Button from '../../components/Button.jsx';
import DataTable from '../../components/DataTable.jsx';
import Dialog from '../../components/Dialog.jsx';
import { SelectInput, TextArea, TextInput } from '../../components/Field.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Panel, { Banner } from '../../components/Panel.jsx';
import SidePanel from '../../components/SidePanel.jsx';
import { EmptyState } from '../../components/States.jsx';
import { ACTIONS } from './copy.js';
import styles from './Standards.module.css';

const REVIEW_TONE = { 초안: 'neutral', '검토 완료': 'success', '사용 중지': 'warning' };

/** AD-13 조치 제안 표 (유형 B + D): 운영자가 행을 골라 고치고 검토 상태를 바꾼다. 검토 완료인 행만 사용자 화면에 쓴다. */
export default function ActionsPage() {
  const state = useAsync(() => getActionTable(), []);
  const [editing, setEditing] = useState(null);
  const [saved, setSaved] = useState('');
  const [article, setArticle] = useState(null);
  const [viewed, setViewed] = useState({});
  const [busyDraft, setBusyDraft] = useState(null);

  const download = (rows) => {
    downloadCsv('RADAR_조치제안표.csv', [ACTIONS.head, ...rows.map((r) => [r.ck, r.problem, r.check, r.action, r.sentence, r.dept || ACTIONS.deptNone, r.article || ACTIONS.articleNone, r.review])]);
    recordAdminDownload({ name: '조치 제안 표' });
  };

  const openArticle = async (draft) => {
    const a = await getDraftArticle({ draftId: draft.id });
    setArticle(a);
    setViewed((v) => ({ ...v, [draft.id]: true }));
  };
  const saveDraft = async (draft) => {
    setBusyDraft(draft.id);
    try {
      const r = await saveActionDraft({ draftId: draft.id });
      setSaved(r.ck);
      setArticle(null);
      state.reload();
    } finally {
      setBusyDraft(null);
    }
  };

  return (
    <div>
      <PageHeader title={ACTIONS.title} subtitle={ACTIONS.subtitle} />
      <Loadable state={state} areaName={ACTIONS.failedArea} rows={6}>
        {(d) => (
          <div className={styles.row}>
            <div className={`${styles.stack} ${styles.main}`}>
              {saved ? <Banner tone="success">{ACTIONS.saved(saved)}</Banner> : null}
              <Panel padded={false}>
                <div className={styles.tableHead}>
                  <p className={styles.note}>{ACTIONS.note}</p>
                  <button type="button" className={styles.linkBtn} onClick={() => download(d.rows)}>
                    {ACTIONS.download}
                  </button>
                </div>
                <DataTable
                  caption={ACTIONS.caption}
                  columns={[
                    { key: 'ck', header: ACTIONS.head[0], first: true, nowrap: true, width: 100 },
                    { key: 'problem', header: ACTIONS.head[1], width: 200 },
                    { key: 'check', header: ACTIONS.head[2], width: 170 },
                    { key: 'action', header: ACTIONS.head[3], width: 180 },
                    { key: 'sentence', header: ACTIONS.head[4], width: 340 },
                    { key: 'dept', header: ACTIONS.head[5], width: 170, render: (r) => r.dept || <span className={styles.note}>{ACTIONS.deptNone}</span> },
                    { key: 'article', header: ACTIONS.head[6], width: 190, render: (r) => r.article || <span className={styles.note}>{ACTIONS.articleNone}</span> },
                    { key: 'review', header: ACTIONS.head[7], width: 130, render: (r) => <Badge tone={REVIEW_TONE[r.review]}>{r.review}</Badge> },
                    {
                      key: 'edit',
                      header: <span className="sr-only">동작</span>,
                      width: 150,
                      align: 'right',
                      render: (r) => (
                        <Button compact variant="secondary" onClick={() => setEditing(r)} aria-label={`${r.ck} ${ACTIONS.editRow}`}>
                          {ACTIONS.editRow}
                        </Button>
                      ),
                    },
                  ]}
                  rows={d.rows}
                  getRowKey={(r) => r.id}
                />
              </Panel>
              <Panel title={ACTIONS.draftTitle}>
                {d.drafts.length === 0 ? (
                  <EmptyState text={ACTIONS.draftEmpty} />
                ) : (
                  d.drafts.map((draft) => (
                    <div key={draft.id} className={styles.draft}>
                      <p className={styles.draftText}>{`${draft.problem} · ${draft.sentence}`}</p>
                      <p className={styles.draftBasis}>{ACTIONS.draftArticle(draft.article)}</p>
                      <button type="button" className={styles.linkBtn} onClick={() => openArticle(draft)}>
                        {ACTIONS.viewArticle}
                      </button>
                      {/* 운영자가 원문과 대조한 뒤에만 저장할 수 있다 */}
                      <div>
                        <Button variant="primary" loading={busyDraft === draft.id} disabled={!viewed[draft.id]} onClick={() => saveDraft(draft)}>
                          {ACTIONS.draftSave}
                        </Button>
                      </div>
                    </div>
                  ))
                )}
                <p className={styles.note}>{ACTIONS.draftNote}</p>
              </Panel>
            </div>
            {article ? (
              <SidePanel title={article.title} titleId="draft-article-title" onClose={() => setArticle(null)} closeLabel={ACTIONS.articleClose}>
                {article.text}
              </SidePanel>
            ) : null}
            {editing ? (
              <EditDialog
                row={editing}
                onClose={() => setEditing(null)}
                onSaved={(ck) => {
                  setSaved(ck);
                  setEditing(null);
                  state.reload();
                }}
              />
            ) : null}
          </div>
        )}
      </Loadable>
    </div>
  );
}

function EditDialog({ row, onClose, onSaved }) {
  const [f, setF] = useState({ check: row.check, action: row.action, sentence: row.sentence, dept: row.dept || '', article: row.article || '', review: row.review });
  const [busy, setBusy] = useState(false);
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));
  const save = async () => {
    setBusy(true);
    try {
      const r = await saveActionRow({ id: row.id, patch: { ...f, dept: f.dept.trim() || null, article: f.article.trim() || null } });
      if (r.ok) onSaved(r.ck);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog
      title={ACTIONS.editTitle(row.ck)}
      titleId="edit-action-title"
      subtitle={row.problem}
      size="md"
      onClose={onClose}
      closeLabel={ACTIONS.editClose}
      footer={
        <Button variant="primary" loading={busy} disabled={!f.sentence.trim()} onClick={save}>
          {ACTIONS.editSave}
        </Button>
      }
    >
      <TextInput label={ACTIONS.fCheck} value={f.check} onChange={set('check')} />
      <TextInput label={ACTIONS.fAction} value={f.action} onChange={set('action')} />
      <TextArea label={ACTIONS.fSentence} value={f.sentence} onChange={set('sentence')} rows={4} required />
      <TextInput label={ACTIONS.fDept} value={f.dept} onChange={set('dept')} />
      <TextInput label={ACTIONS.fArticle} value={f.article} onChange={set('article')} />
      <SelectInput label={ACTIONS.fReview} value={f.review} onChange={set('review')} options={ACTIONS.reviewStates} />
    </Dialog>
  );
}
