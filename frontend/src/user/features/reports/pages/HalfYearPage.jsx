import { getHalfYearSummary } from '../../../../api/reports.js';
import { useAsync } from '../../../../shared/hooks/useAsync.js';
import { useAuth } from '../../../../app/providers/AuthProvider.jsx';
import { useRun } from '../../../../app/providers/RunProvider.jsx';
import { ROLE } from '../../../../shared/constants.js';
import { runYear } from '../../../../shared/utils/format.js';
import PageHeader from '../../../components/PageHeader.jsx';
import { ErrorState, SkeletonRows } from '../../../components/States.jsx';
import { HALF } from '../copy.js';
import { DownloadBar, ReportCard, ReportShell, RowList, fileHeader, useReportDownload } from '../components/ReportParts.jsx';

/** US-09 반기 변경 요약. 확정한 대상은 바꾸지 않는다. */
export default function HalfYearPage() {
  const { user } = useAuth();
  const { run } = useRun();
  const { data, failed, loading, showSkeleton, reload } = useAsync(() => getHalfYearSummary({ runId: run.id }), [run.id, user.id]);
  const changed = data?.changedData.map((d) => HALF.changedRow(d.name, d.from, d.to)) ?? [];
  const ranks = data?.rankChanges.map((c) => HALF.rankRow(c.address, c.from, c.to)) ?? [];
  const targets = data?.changedTargets.map((c) => HALF.targetRow(c.address, c.changed)) ?? [];
  const dl = useReportDownload({
    reportName: HALF.reportName,
    guLabel: user.role === ROLE.CITY ? '3개구' : user.gu,
    header: fileHeader(run),
    table: [[HALF.changedTitle], ...changed.map((x) => [x]), [HALF.rankTitle], ...ranks.map((x) => [x]), [HALF.targetTitle], ...targets.map((x) => [x])],
    withComplaintSource: run.hasComplaints,
  });
  return (
    <ReportShell>
      <PageHeader title={HALF.title(runYear(run.name))} subtitle={HALF.subtitle} />
      {failed ? (
        <ReportCard>
          <ErrorState areaName={HALF.reportName} onRetry={reload} />
        </ReportCard>
      ) : loading && !data ? (
        showSkeleton ? (
          <ReportCard>
            <SkeletonRows rows={5} />
          </ReportCard>
        ) : null
      ) : (
        <>
          <ReportCard title={HALF.changedTitle}>
            {changed.length ? <RowList items={changed} /> : <p style={{ color: 'var(--semantic-color-text-muted)' }}>{HALF.changedEmpty}</p>}
          </ReportCard>
          <ReportCard title={HALF.rankTitle}>
            <RowList items={ranks} />
          </ReportCard>
          <ReportCard title={HALF.targetTitle}>
            <RowList items={targets} />
          </ReportCard>
        </>
      )}
      {data ? <DownloadBar reportName={HALF.reportName} dl={dl} /> : null}
    </ReportShell>
  );
}
