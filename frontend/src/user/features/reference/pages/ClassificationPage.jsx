import { listClassifySamples, markClassify } from '../../../../api/reference.js';
import { Navigate } from 'react-router-dom';
import { useAsync } from '../../../../shared/hooks/useAsync.js';
import { useRun } from '../../../../app/providers/RunProvider.jsx';
import { useAuth } from '../../../../app/providers/AuthProvider.jsx';
import Button from '../../../components/Button.jsx';
import DataTable from '../../../components/DataTable.jsx';
import PageHeader from '../../../components/PageHeader.jsx';
import Tag from '../../../components/Tag.jsx';
import { SelectField } from '../../../components/FormControls.jsx';
import { ErrorState, SkeletonRows } from '../../../components/States.jsx';
import { COMMON } from '../../../../shared/copy/common.js';
import { CLASSIFY } from '../copy.js';
import { useState } from 'react';
import styles from './Reference.module.css';

/** US-11 분류 검수 (도로관리팀, 조건부). 원문은 보이지 않고 가린 요약만 보인다 (공통 규칙 15번). */
export default function ClassificationPage() {
  const { user } = useAuth();
  const { run } = useRun();
  const { data, failed, loading, showSkeleton, reload } = useAsync(() => listClassifySamples({ runId: run.id }), [run.id, user.id]);
  const [fixingId, setFixingId] = useState(null);

  // 민원 자료가 없는 회차에는 이 화면을 쓰지 않는다 (메뉴도 숨긴다)
  if (data && !data.available) return <Navigate to="/candidates" replace />;

  const save = async (id, result, label) => {
    await markClassify({ id, result, label });
    setFixingId(null);
    reload();
  };

  const columns = [
    { key: 'summary', header: CLASSIFY.head[0], width: 340, render: (r) => r.summary },
    { key: 'label', header: CLASSIFY.head[1], width: 200, render: (r) => (r.done?.label ? r.done.label : r.label) },
    { key: 'kw', header: CLASSIFY.head[2], width: 160, render: (r) => r.keywords },
    {
      key: 'act',
      header: <span className="sr-only">검수</span>,
      align: 'right',
      render: (r) => {
        if (r.done) return <Tag tone={r.done.result === '맞음' ? 'low' : 'info'} small>{r.done.result === '맞음' ? CLASSIFY.doneOk : CLASSIFY.doneFix}</Tag>;
        if (fixingId === r.id) {
          return (
            <SelectField
              inline={false}
              label={CLASSIFY.fixLabel}
              id={`fix-${r.id}`}
              value={r.label}
              onChange={(v) => save(r.id, '고침', v)}
              options={data.labels}
            />
          );
        }
        return (
          <span className={styles.rowBtns}>
            <Button variant="soft" onClick={() => save(r.id, '맞음', null)}>
              {CLASSIFY.ok}
            </Button>
            <Button variant="soft" onClick={() => setFixingId(r.id)}>
              {CLASSIFY.fix}
            </Button>
          </span>
        );
      },
    },
  ];

  return (
    <div>
      <PageHeader title={CLASSIFY.title} subtitle={CLASSIFY.subtitle} />
      <section className={styles.card}>
        {failed ? (
          <ErrorState areaName="분류 표본" onRetry={reload} />
        ) : loading && !data ? (
          showSkeleton ? <SkeletonRows rows={6} /> : null
        ) : (
          <>
            <div className={styles.scroll}>
              <DataTable caption={CLASSIFY.title} columns={columns} rows={data.items} getRowKey={(r) => r.id} />
            </div>
            <p className={styles.source}>{COMMON.sourceComplaint}</p>
          </>
        )}
      </section>
    </div>
  );
}
