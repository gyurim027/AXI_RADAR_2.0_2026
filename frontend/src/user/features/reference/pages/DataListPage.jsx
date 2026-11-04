import { listDataList } from '../../../../api/reference.js';
import { useAsync } from '../../../../shared/hooks/useAsync.js';
import DataTable from '../../../components/DataTable.jsx';
import PageHeader from '../../../components/PageHeader.jsx';
import Tag from '../../../components/Tag.jsx';
import { ErrorState, SkeletonRows } from '../../../components/States.jsx';
import { DATA } from '../copy.js';
import styles from './Reference.module.css';

const FRESH_TONE = { 최신: 'low', '갱신 예정일 지남': 'mid', 빠짐: 'high' };

/** US-12 데이터 목록. 보기만 한다. 결과물 공유 조건을 보여준다. */
export default function DataListPage() {
  const { data, failed, loading, showSkeleton, reload } = useAsync(() => listDataList(), []);
  const H = DATA.head;
  const columns = [
    { key: 'name', header: H[0], render: (d) => d.name },
    { key: 'org', header: H[1], render: (d) => d.org },
    {
      key: 'basis',
      header: H[2],
      render: (d) => (
        <span>
          {d.basis}
          {d.updateType === '1회성' ? (
            <>
              {' '}
              <Tag tone="mid" small>
                과거 기록
              </Tag>
            </>
          ) : null}
        </span>
      ),
    },
    { key: 'fresh', header: H[3], render: (d) => <Tag tone={FRESH_TONE[d.freshness]} small>{d.freshness}</Tag> },
    { key: 'share', header: H[4], render: (d) => d.share },
  ];
  return (
    <div>
      <PageHeader title={DATA.title} subtitle={DATA.subtitle} />
      <section className={styles.card}>
        {failed ? (
          <ErrorState areaName={DATA.title} onRetry={reload} />
        ) : loading && !data ? (
          showSkeleton ? <SkeletonRows rows={8} /> : null
        ) : (
          <div className={styles.scroll}>
            <DataTable caption={DATA.title} columns={columns} rows={data} getRowKey={(d) => d.id} />
          </div>
        )}
      </section>
    </div>
  );
}
