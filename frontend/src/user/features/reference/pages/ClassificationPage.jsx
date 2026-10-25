import { listClassifySamples, markClassify } from '../../../../api/reference.js';
import { Navigate } from 'react-router-dom';
import { useAsync } from '../../../../shared/hooks/useAsync.js';
import { useRun } from '../../../../app/providers/RunProvider.jsx';
import { useAuth } from '../../../../app/providers/AuthProvider.jsx';
import Button from '../../../components/Button.jsx';
import DataTable from '../../../components/DataTable.jsx';
import PageHeader from '../../../components/PageHeader.jsx';
import Tag from '../../../components/Tag.jsx';
import { ErrorState, SkeletonRows } from '../../../components/States.jsx';
import { COMMON } from '../../../../shared/copy/common.js';
import { CLASSIFY } from '../copy.js';
import styles from './Reference.module.css';

/** US-11 분류 검수 (도로관리팀, 조건부). 원문은 보이지 않고 가린 요약만 보인다 (공통 규칙 15번). */
export default function ClassificationPage() {
  const { user } = useAuth();
  const { run } = useRun();
  const { data, failed, loading, showSkeleton, reload } = useAsync(() => listClassifySamples({ runId: run.id }), [run.id, user.id]);
  // 민원 자료가 없는 회차에는 이 화면을 쓰지 않는다 (메뉴도 숨긴다)
  if (data && !data.available) return <Navigate to="/candidates" replace />;

  // 도로관리팀은 분류가 맞는지 확인만 한다. 고치는 일은 RADAR 운영자(AD-05)가 한다.
  const confirm = async (id) => {
    await markClassify({ id, result: '맞음', label: null });
    reload();
  };

  const columns = [
    { key: 'summary', header: CLASSIFY.head[0], width: 340, render: (r) => r.summary },
    { key: 'label', header: CLASSIFY.head[1], width: 200, render: (r) => r.label },
    { key: 'kw', header: CLASSIFY.head[2], width: 160, render: (r) => r.keywords },
    {
      key: 'act',
      header: <span className="sr-only">검수</span>,
      align: 'right',
      render: (r) => {
        if (user.readOnly && !r.done) return null; // 보기 전용에서는 확인 버튼을 숨긴다
        if (r.done) return <Tag tone="low" small>{CLASSIFY.doneOk}</Tag>;
        return (
          <Button variant="soft" onClick={() => confirm(r.id)}>
            {CLASSIFY.ok}
          </Button>
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
