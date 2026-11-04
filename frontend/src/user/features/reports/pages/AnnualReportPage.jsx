import { useNavigate } from 'react-router-dom';
import { getAnnualReport } from '../../../../api/reports.js';
import { useAsync } from '../../../../shared/hooks/useAsync.js';
import { backendAuthEnabled, priorityBackendEnabled } from '../../../../api/backend.js';
import { useAuth } from '../../../../app/providers/AuthProvider.jsx';
import { useRun } from '../../../../app/providers/RunProvider.jsx';
import { runYear } from '../../../../shared/utils/format.js';
import Button from '../../../components/Button.jsx';
import DataTable from '../../../components/DataTable.jsx';
import PageHeader from '../../../components/PageHeader.jsx';
import Tag from '../../../components/Tag.jsx';
import { EmptyState, ErrorState, SkeletonRows } from '../../../components/States.jsx';
import { ANNUAL, DOWNLOAD } from '../copy.js';
import { DownloadBar, ReportCard, ReportShell, fileHeader, useReportDownload } from '../components/ReportParts.jsx';
import PreviewGroups from '../components/PreviewGroups.jsx';
import styles from '../components/ReportParts.module.css';

// 서버 연결 모드는 1차 범위가 미리보기 전용이다: 파일 내려받기와 자동 발송이 없다(결정 2-14, D5).
const PREVIEW_ONLY = backendAuthEnabled && priorityBackendEnabled;

/** US-05 관할 부서별 연간 보고서 (도로관리팀, 자기 구만) */
export default function AnnualReportPage() {
  const { user } = useAuth();
  const { run } = useRun();
  const navigate = useNavigate();
  const { data, failed, loading, showSkeleton, reload } = useAsync(() => getAnnualReport({ runId: run.id }), [run.id, user.id]);
  const rows = data?.rows ?? [];
  const table = [ANNUAL.head, ...rows.map((r) => [r.dept, ANNUAL.rowCount(r.count)])];
  const dl = useReportDownload({
    reportName: ANNUAL.reportName,
    guLabel: user.gu,
    header: fileHeader(run, [`구: ${user.gu}`]),
    table,
    withComplaintSource: run.hasComplaints,
  });

  const columns = [
    { key: 'dept', header: ANNUAL.head[0], render: (r) => r.dept },
    { key: 'count', header: ANNUAL.head[1], render: (r) => <span className="num">{ANNUAL.rowCount(r.count)}</span> },
    PREVIEW_ONLY ? null : {
      key: 'file',
      header: <span className="sr-only">부서별 내려받기</span>,
      render: (r) => {
        const rowsOne = [ANNUAL.head, [r.dept, ANNUAL.rowCount(r.count)]];
        return (
          <span className={styles.rowBtns}>
            <Button variant="text" disabled={!!dl.busy} aria-label={`${r.dept} ${DOWNLOAD.pdfLabel(ANNUAL.reportName)}`} onClick={() => dl.go('pdf', { onlyDept: r.dept, rows: rowsOne })}>
              PDF
            </Button>
            <Button variant="text" disabled={!!dl.busy} aria-label={`${r.dept} ${DOWNLOAD.excelLabel(ANNUAL.reportName)}`} onClick={() => dl.go('excel', { onlyDept: r.dept, rows: rowsOne })}>
              엑셀
            </Button>
          </span>
        );
      },
    },
  ].filter(Boolean);

  return (
    <ReportShell>
      <PageHeader title={ANNUAL.title(runYear(run.name))} subtitle={PREVIEW_ONLY ? ANNUAL.subtitlePreview : ANNUAL.subtitle}>
        {PREVIEW_ONLY ? <Tag tone="info">{ANNUAL.previewTag}</Tag> : null}
      </PageHeader>
      {PREVIEW_ONLY && data?.ready ? (
        <>
          <PreviewGroups groups={data.groups ?? []} />
          <p className={styles.note}>{ANNUAL.previewNote}</p>
        </>
      ) : (
        <ReportCard>
          {failed ? (
            <ErrorState areaName={ANNUAL.reportName} onRetry={reload} />
          ) : loading && !data ? (
            showSkeleton ? <SkeletonRows rows={4} /> : null
          ) : data.ready ? (
            <>
              <DataTable caption={ANNUAL.reportName} columns={columns} rows={rows} getRowKey={(r) => r.dept} />
              <p className={styles.note}>{PREVIEW_ONLY ? ANNUAL.previewNote : ANNUAL.notSend}</p>
            </>
          ) : (
            <EmptyState text={ANNUAL.empty} actionLabel={ANNUAL.goDecide} onAction={() => navigate('/candidates')} />
          )}
        </ReportCard>
      )}
      {data?.ready && !PREVIEW_ONLY ? <DownloadBar reportName={ANNUAL.reportName} dl={dl} /> : null}
    </ReportShell>
  );
}
