import { listRegulations } from '../../../../api/reference.js';
import { useAsync } from '../../../../shared/hooks/useAsync.js';
import DataTable from '../../../components/DataTable.jsx';
import PageHeader from '../../../components/PageHeader.jsx';
import { EmptyState, ErrorState, SkeletonRows } from '../../../components/States.jsx';
import { REGS } from '../copy.js';
import styles from './Reference.module.css';

/** US-13 규정 변경. 보기만 한다. 날짜 순. */
export default function RegulationsPage() {
  const { data, failed, loading, showSkeleton, reload } = useAsync(() => listRegulations(), []);
  const H = REGS.head;
  const rows = data ? [...data].sort((a, b) => (a.date < b.date ? 1 : -1)) : [];
  const columns = [
    { key: 'name', header: H[0], render: (r) => r.name },
    { key: 'changed', header: H[1], render: (r) => r.changed },
    { key: 'date', header: H[2], render: (r) => <span className="num">{r.date}</span> },
  ];
  return (
    <div>
      <PageHeader title={REGS.title} subtitle={REGS.subtitle} />
      <section className={styles.card}>
        {failed ? (
          <ErrorState areaName={REGS.title} onRetry={reload} />
        ) : loading && !data ? (
          showSkeleton ? <SkeletonRows rows={4} /> : null
        ) : rows.length === 0 ? (
          <EmptyState text={REGS.empty} />
        ) : (
          <DataTable caption={REGS.title} columns={columns} rows={rows} getRowKey={(r) => r.id} />
        )}
      </section>
    </div>
  );
}
