import { listSchedule } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import DataTable from '../../components/DataTable.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import { SCHEDULE } from './copy.js';

/** AD-08 실행 일정 (유형 B, 조회 전용): 연 1회 산정과 반기 수집 일정. 자동 실행은 확장 단계라 일정만 보여 준다. */
export default function SchedulePage() {
  const state = useAsync(() => listSchedule(), []);
  return (
    <div>
      <PageHeader title={SCHEDULE.title} subtitle={SCHEDULE.subtitle} />
      <Loadable state={state} areaName={SCHEDULE.failedArea} rows={3}>
        {(rows) => (
          <DataTable
            caption={SCHEDULE.caption}
            columns={[
              { key: 'name', header: SCHEDULE.head[0], first: true },
              { key: 'cycle', header: SCHEDULE.head[1], nowrap: true },
              { key: 'next', header: SCHEDULE.head[2], nowrap: true },
              { key: 'last', header: SCHEDULE.head[3], nowrap: true },
            ]}
            rows={rows}
            getRowKey={(r) => r.id}
          />
        )}
      </Loadable>
    </div>
  );
}
