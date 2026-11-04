import { getConditionRecord } from '../../../../api/reports.js';
import { useAsync } from '../../../../shared/hooks/useAsync.js';
import { useAuth } from '../../../../app/providers/AuthProvider.jsx';
import { useRun } from '../../../../app/providers/RunProvider.jsx';
import { ROLE } from '../../../../shared/constants.js';
import { runYear } from '../../../../shared/utils/format.js';
import { InfoHelp } from '../../../components/FormControls.jsx';
import PageHeader from '../../../components/PageHeader.jsx';
import DataTable from '../../../components/DataTable.jsx';
import { ErrorState, SkeletonRows } from '../../../components/States.jsx';
import { CONDITION } from '../copy.js';
import { DownloadBar, ReportCard, ReportShell, fileHeader, useReportDownload } from '../components/ReportParts.jsx';

/** US-07 산정 조건 기록서. 3개 구가 모두 확정해 회차가 확정될 때 남는다. */
export default function ConditionRecordPage() {
  const { user } = useAuth();
  const { run } = useRun();
  const { data, failed, loading, showSkeleton, reload } = useAsync(() => getConditionRecord({ runId: run.id }), [run.id, user.id]);
  // 서버 연결 모드의 값에는 가짜 서버용 필드(unratedFields)가 없다. 그 화면은 아래 ServerConditionView가 그린다.
  const line = data?.ready && !data.server ? CONDITION.body(data.dataCount, data.version, data.unratedFields.join(', '), data.conditionCount) : null;
  const dl = useReportDownload({
    reportName: CONDITION.reportName,
    guLabel: user.role === ROLE.CITY ? '3개구' : user.gu,
    header: fileHeader(run),
    table: [[line || '']],
    withComplaintSource: run.hasComplaints,
  });
  const empty = user.role === ROLE.CITY ? CONDITION.emptyCity : CONDITION.emptyDistrict;

  return (
    <ReportShell>
      <PageHeader title={CONDITION.title(runYear(run.name))} subtitle={CONDITION.subtitle} />
      <ReportCard>
        {failed ? (
          <ErrorState areaName={CONDITION.reportName} onRetry={reload} />
        ) : loading && !data ? (
          showSkeleton ? <SkeletonRows rows={2} /> : null
        ) : data.server ? (
          <ServerConditionView data={data} empty={empty} />
        ) : data.ready ? (
          <p>
            {line}
            <InfoHelp label="평가하지 못한 분야 뜻 보기">자료가 없어 평가하지 못한 분야입니다. 0점으로 처리하지 않았습니다.</InfoHelp>
          </p>
        ) : (
          <p style={{ color: 'var(--semantic-color-text-muted)' }}>{empty}</p>
        )}
      </ReportCard>
      {data?.ready && !data.server ? <DownloadBar reportName={CONDITION.reportName} dl={dl} /> : null}
    </ReportShell>
  );
}

/** 서버 연결 모드: 점수 모델 결과로 만든 점수 근거. 파일 내려받기는 배포 후라 보이지 않는다. */
function ServerConditionView({ data, empty }) {
  if (!data.ready) return <p style={{ color: 'var(--semantic-color-text-muted)' }}>{empty}</p>;
  const muted = { color: 'var(--semantic-color-text-muted)' };
  return (
    <div style={{ display: 'grid', gap: 24 }}>
      <p>{CONDITION.summary(data.version, data.candidateCount, data.priorityCount)}</p>
      {data.dataCount == null ? <p style={muted}>{CONDITION.dataCountUnknown}</p> : null}
      <section aria-label={CONDITION.scoreTitle}>
        <h3>{CONDITION.scoreTitle}</h3>
        <p>{CONDITION.scoreBody}</p>
        <DataTable
          caption={CONDITION.scoreTitle}
          columns={[
            { key: 'domain', header: CONDITION.indicatorHead[0], width: 90, render: (r) => r.domain },
            { key: 'label', header: CONDITION.indicatorHead[1], render: (r) => r.label },
          ]}
          rows={data.indicators}
          getRowKey={(r) => r.label}
        />
      </section>
      <section aria-label={CONDITION.conditionTitle}>
        <h3>{CONDITION.conditionTitle}</h3>
        <p>{CONDITION.conditionBody}</p>
      </section>
      <section aria-label={CONDITION.reliabilityTitle}>
        <h3>{CONDITION.reliabilityTitle}</h3>
        <p>{CONDITION.reliabilityBody}</p>
      </section>
      <section aria-label={CONDITION.unratedTitle}>
        <h3>{CONDITION.unratedTitle}</h3>
        <p>{CONDITION.unratedBody}</p>
        <ul>
          {CONDITION.unratedReasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
        <p>{data.unrated.map((u) => CONDITION.unratedCount(u.name, u.count)).join(' · ')}</p>
      </section>
    </div>
  );
}
