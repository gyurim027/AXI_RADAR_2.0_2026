import { listActionTable } from '../../../../api/reference.js';
import { useAsync } from '../../../../shared/hooks/useAsync.js';
import DataTable from '../../../components/DataTable.jsx';
import PageHeader from '../../../components/PageHeader.jsx';
import Tag from '../../../components/Tag.jsx';
import { ErrorState, SkeletonRows } from '../../../components/States.jsx';
import { ACTIONS } from '../copy.js';
import styles from './Reference.module.css';

/** US-14 조치 제안 표. 보기만 한다. 원본은 대장 05_03 조치 제안 표다. */
export default function ActionsPage() {
  const { data, failed, loading, showSkeleton, reload } = useAsync(() => listActionTable(), []);
  const H = ACTIONS.head;
  const columns = [
    { key: 'problem', header: H[0], width: 200, render: (r) => r.problem },
    { key: 'check', header: H[1], width: 170, render: (r) => r.check },
    { key: 'action', header: H[2], width: 190, render: (r) => r.action },
    { key: 'sentence', header: H[3], width: 380, render: (r) => r.sentence },
    {
      key: 'dept',
      header: H[4],
      width: 180,
      render: (r) =>
        r.dept ? (
          r.dept
        ) : (
          <Tag tone="mid" small>
            {ACTIONS.deptCheck}
          </Tag>
        ),
    },
    { key: 'article', header: H[5], width: 190, render: (r) => r.article || ACTIONS.articlePending },
  ];
  return (
    <div>
      <PageHeader title={ACTIONS.title} subtitle={ACTIONS.subtitle} />
      <section className={styles.card}>
        {failed ? (
          <ErrorState areaName={ACTIONS.title} onRetry={reload} />
        ) : loading && !data ? (
          showSkeleton ? <SkeletonRows rows={5} /> : null
        ) : (
          <div className={styles.scroll}>
            <DataTable caption={ACTIONS.title} columns={columns} rows={data} getRowKey={(r) => r.id} minWidth={1300} />
          </div>
        )}
      </section>
    </div>
  );
}
