import { getBasisTable } from '../../../../api/reports.js';
import { useAsync } from '../../../../shared/hooks/useAsync.js';
import { useAuth } from '../../../../app/providers/AuthProvider.jsx';
import { useRun } from '../../../../app/providers/RunProvider.jsx';
import { ROLE } from '../../../../shared/constants.js';
import { runYear } from '../../../../shared/utils/format.js';
import DataTable from '../../../components/DataTable.jsx';
import PageHeader from '../../../components/PageHeader.jsx';
import { ErrorState, SkeletonRows } from '../../../components/States.jsx';
import { BASIS } from '../copy.js';
import { DownloadBar, ReportCard, ReportShell, fileHeader, useReportDownload } from '../components/ReportParts.jsx';

/** US-06 구별 우선 점검 근거표 (시 도로과는 3개 구를 한 표로, 도로관리팀은 자기 구만) */
export default function BasisPage() {
  const { user } = useAuth();
  const { run } = useRun();
  const { data, failed, loading, showSkeleton, reload } = useAsync(() => getBasisTable({ runId: run.id }), [run.id, user.id]);
  const rows = data?.rows ?? [];
  const guLabel = user.role === ROLE.CITY ? '3개구' : user.gu;
  const table = [BASIS.head, ...rows.map((r) => [r.gu, BASIS.count(r.candidates), BASIS.count(r.targets), r.basis])];
  const dl = useReportDownload({ reportName: BASIS.reportName, guLabel, header: fileHeader(run), table, withComplaintSource: run.hasComplaints });

  const columns = [
    { key: 'gu', header: BASIS.head[0], render: (r) => r.gu },
    { key: 'cand', header: BASIS.head[1], align: 'right', render: (r) => <span className="num">{BASIS.count(r.candidates)}</span> },
    { key: 'target', header: BASIS.head[2], align: 'right', render: (r) => <span className="num">{BASIS.count(r.targets)}</span> },
    { key: 'basis', header: BASIS.head[3], render: (r) => r.basis },
  ];
  const draftEmpty = user.role === ROLE.CITY ? BASIS.draftEmptyCity : BASIS.draftEmptyDistrict;

  return (
    <ReportShell>
      <PageHeader title={BASIS.title(runYear(run.name))} subtitle={BASIS.subtitle} />
      <ReportCard>
        {failed ? (
          <ErrorState areaName={BASIS.reportName} onRetry={reload} />
        ) : loading && !data ? (
          showSkeleton ? <SkeletonRows rows={4} /> : null
        ) : (
          <DataTable caption={BASIS.reportName} columns={columns} rows={rows} getRowKey={(r) => r.gu} />
        )}
      </ReportCard>
      <ReportCard title={BASIS.draftTitle}>
        {data?.draftReady ? <p>{BASIS.draftBody}</p> : data ? <p style={{ color: 'var(--semantic-color-text-muted)' }}>{draftEmpty}</p> : null}
      </ReportCard>
      {data ? <DownloadBar reportName={BASIS.reportName} dl={dl} /> : null}
    </ReportShell>
  );
}
