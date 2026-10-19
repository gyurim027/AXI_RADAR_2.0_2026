import { getConditionRecord } from '../../../../api/reports.js';
import { useAsync } from '../../../../shared/hooks/useAsync.js';
import { useAuth } from '../../../../app/providers/AuthProvider.jsx';
import { useRun } from '../../../../app/providers/RunProvider.jsx';
import { ROLE } from '../../../../shared/constants.js';
import { runYear } from '../../../../shared/utils/format.js';
import PageHeader from '../../../components/PageHeader.jsx';
import { ErrorState, SkeletonRows } from '../../../components/States.jsx';
import { CONDITION } from '../copy.js';
import { DownloadBar, ReportCard, ReportShell, fileHeader, useReportDownload } from '../components/ReportParts.jsx';

/** US-07 산정 조건 기록서. 3개 구가 모두 확정해 회차가 확정될 때 남는다. */
export default function ConditionRecordPage() {
  const { user } = useAuth();
  const { run } = useRun();
  const { data, failed, loading, showSkeleton, reload } = useAsync(() => getConditionRecord({ runId: run.id }), [run.id, user.id]);
  const line = data?.ready ? CONDITION.body(data.dataCount, data.version, data.unratedFields.join(', '), data.conditionCount) : null;
  const dl = useReportDownload({
    reportName: CONDITION.reportName,
    guLabel: user.role === ROLE.CITY ? '3개구' : user.gu,
    header: fileHeader(run),
    table: [[line || '']],
    withComplaintSource: run.hasComplaints,
  });
  const empty = user.role === ROLE.CITY ? CONDITION.emptyCity : CONDITION.emptyDistrict(run.name);

  return (
    <ReportShell>
      <PageHeader title={CONDITION.title(runYear(run.name))} subtitle={CONDITION.subtitle} />
      <ReportCard>
        {failed ? (
          <ErrorState areaName={CONDITION.reportName} onRetry={reload} />
        ) : loading && !data ? (
          showSkeleton ? <SkeletonRows rows={2} /> : null
        ) : data.ready ? (
          <p>{line}</p>
        ) : (
          <p style={{ color: 'var(--semantic-color-text-muted)' }}>{empty}</p>
        )}
      </ReportCard>
      {data?.ready ? <DownloadBar reportName={CONDITION.reportName} dl={dl} /> : null}
    </ReportShell>
  );
}
