import { getProtectionCompare } from '../../../../api/reports.js';
import { useAsync } from '../../../../shared/hooks/useAsync.js';
import { useAuth } from '../../../../app/providers/AuthProvider.jsx';
import { useRun } from '../../../../app/providers/RunProvider.jsx';
import { runYear } from '../../../../shared/utils/format.js';
import DataTable from '../../../components/DataTable.jsx';
import PageHeader from '../../../components/PageHeader.jsx';
import { ErrorState, SkeletonRows } from '../../../components/States.jsx';
import { PROTECTION } from '../copy.js';
import { DownloadBar, ReportCard, ReportShell, fileHeader, useReportDownload } from '../components/ReportParts.jsx';

/** US-08 보호구역 안팎 비교표 (시 도로과만). 시 도로과가 교통시설팀에 보낸다. */
export default function ProtectionZonePage() {
  const { user } = useAuth();
  const { run } = useRun();
  const { data, failed, loading, showSkeleton, reload } = useAsync(() => getProtectionCompare({ runId: run.id }), [run.id, user.id]);
  const rows = data
    ? [
        { key: 'in', label: '보호구역 안', text: PROTECTION.inside(data.inside) },
        { key: 'out', label: '보호구역 밖', text: PROTECTION.outside(data.outside) },
      ]
    : [];
  const dl = useReportDownload({
    reportName: PROTECTION.reportName,
    guLabel: '3개구',
    header: fileHeader(run),
    table: [PROTECTION.head, ...(data ? [['보호구역 안', `${data.inside}곳`], ['보호구역 밖', `${data.outside}곳`]] : [])],
    withComplaintSource: false,
  });
  const columns = [
    { key: 'label', header: PROTECTION.head[0], render: (r) => r.label },
    { key: 'n', header: PROTECTION.head[1], render: (r) => <span className="num">{r.key === 'in' ? `${data.inside}곳` : `${data.outside}곳`}</span> },
  ];

  return (
    <ReportShell>
      <PageHeader title={PROTECTION.title(runYear(run.name))} subtitle={PROTECTION.subtitle} />
      <ReportCard>
        {failed ? (
          <ErrorState areaName={PROTECTION.reportName} onRetry={reload} />
        ) : loading && !data ? (
          showSkeleton ? <SkeletonRows rows={2} /> : null
        ) : (
          <DataTable caption={PROTECTION.reportName} columns={columns} rows={rows} getRowKey={(r) => r.key} />
        )}
      </ReportCard>
      {data ? <DownloadBar reportName={PROTECTION.reportName} dl={dl} /> : null}
    </ReportShell>
  );
}
