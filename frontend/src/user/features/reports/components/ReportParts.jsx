import { useState } from 'react';
import Button from '../../../components/Button.jsx';
import { recordDownload } from '../../../../api/reports.js';
import { COMMON } from '../../../../shared/copy/common.js';
import { useRun } from '../../../../app/providers/RunProvider.jsx';
import { runTitle } from '../../../../shared/utils/format.js';
import PageFooterNote from '../../../components/PageFooterNote.jsx';
import { DOWNLOAD } from '../copy.js';
import { makeFile } from '../download.js';
import styles from './ReportParts.module.css';

/** 보고서 화면 뼈대: 화면 머리 → 블록 카드를 세로로 쌓기 → 내려받기. 본문 폭 최대 1000px, 가운데 (디자인 시스템 8장 유형 E) */
export function ReportShell({ children }) {
  return (
    <div className={styles.shell}>
      {children}
      <PageFooterNote />
    </div>
  );
}

export function ReportCard({ title, children, className = '' }) {
  return (
    <section className={`${styles.card} ${className}`}>
      {title ? <h2 className={styles.cardTitle}>{title}</h2> : null}
      {children}
    </section>
  );
}

/** 파일 만들기 상태. 내려받은 기록이 남는다(I-04). 사유는 묻지 않는다. */
export function useReportDownload({ reportName, guLabel, header, table, withComplaintSource }) {
  const { run } = useRun();
  const [busy, setBusy] = useState(null);
  const go = async (format, { onlyDept, rows } = {}) => {
    setBusy(onlyDept ? `${format}:${onlyDept}` : format);
    try {
      await new Promise((r) => setTimeout(r, 900));
      await recordDownload({ runId: run.id, reportName, format });
      makeFile({
        format,
        runName: run.name,
        guLabel,
        reportName: onlyDept ? `${reportName}_${onlyDept}` : reportName,
        header,
        table: rows || table,
        withComplaintSource,
      });
    } finally {
      setBusy(null);
    }
  };
  return { busy, go };
}

/**
 * 파일로 내려받기 (9-1). 만드는 동안 버튼 안에 진행 표시를 넣고 폭은 그대로 둔다.
 * 만드는 중에는 안내 문구를 보인다 (CM-00 13번).
 */
export function DownloadBar({ reportName, dl }) {
  const { busy, go } = dl;
  return (
    <ReportCard title={DOWNLOAD.title}>
      <div className={styles.dl}>
        {busy ? (
          <p className={styles.making} role="status">
            {COMMON.makingFile(reportName)}
          </p>
        ) : null}
        <Button variant="soft" loading={busy === 'pdf'} disabled={!!busy} aria-label={DOWNLOAD.pdfLabel(reportName)} onClick={() => go('pdf')}>
          {DOWNLOAD.pdf}
        </Button>
        <Button variant="soft" loading={busy === 'excel'} disabled={!!busy} aria-label={DOWNLOAD.excelLabel(reportName)} onClick={() => go('excel')}>
          {DOWNLOAD.excel}
        </Button>
      </div>
    </ReportCard>
  );
}

/** 보고서 위쪽에 붙는 줄: 자료 기준일과 산정 기준 버전 (4-4 표시) */
export function fileHeader(run, extra = []) {
  return [`점검 해: ${runTitle(run)}`, `자료 기준일: ${run.dataRange}`, `산정 기준 버전: ${run.version}`, ...extra];
}

/** 한 줄씩 쌓는 표 행 목록 (US-09) */
export function RowList({ items }) {
  return (
    <ul className={styles.rows}>
      {items.map((t) => (
        <li key={t} className={styles.row}>
          {t}
        </li>
      ))}
    </ul>
  );
}
