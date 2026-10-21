import { Link } from 'react-router-dom';
import { getDashboard } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import { useAdmin } from '../../AdminProvider.jsx';
import Badge, { RUN_TONE } from '../../components/Badge.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Panel from '../../components/Panel.jsx';
import { ErrorState, SkeletonRows } from '../../components/States.jsx';
import { DASH } from './copy.js';
import styles from './Dashboard.module.css';

/** 숫자를 누르면 그 상태로 거른 화면으로 간다. 숫자는 크게, 앞뒤 글자는 그대로 읽힌다. */
function Metric({ before, value, after, to }) {
  return (
    <Link to={to} className={styles.metric}>
      {before}
      <span className={styles.value}>{value}</span>
      {after}
    </Link>
  );
}

/** AD-01 대시보드 (유형 A): 맨 위 폭 전체 '다음 할 일' 카드 아래에 카드 격자. 기준일 지난 자료가 있으면 자료 카드를, 실패가 있으면 실행 카드를 맨 위로 올린다. */
export default function DashboardPage() {
  const { run } = useAdmin();
  const { data, failed, showSkeleton, reload } = useAsync(() => getDashboard({ runId: run.id }), [run.id]);

  return (
    <div>
      <PageHeader title={DASH.title} subtitle={DASH.subtitle} />
      {failed ? (
        <Panel aria-label={DASH.title}>
          <ErrorState areaName="대시보드" onRetry={reload} />
        </Panel>
      ) : !data ? (
        showSkeleton ? <SkeletonRows rows={5} /> : null
      ) : (
        <Body data={data} />
      )}
    </div>
  );
}

function Body({ data }) {
  const dataCard = (
    <Panel key="data" title={DASH.dataTitle} className={styles.card}>
      <div className={styles.metrics}>
        <Metric before="기준일 지난 자료 " value={data.data.stale} after="종" to="/admin/data/list?freshness=갱신 예정일 지남" />
        <span aria-hidden="true">·</span>
        <Metric before="빠진 자료 " value={data.data.missing} after="종" to="/admin/data/list?freshness=빠짐" />
      </div>
    </Panel>
  );
  const runCard = (
    <Panel key="runs" title={DASH.runsTitle} className={styles.card}>
      <div className={styles.metrics}>
        <span>{`최근 ${data.runs.days}일`}</span>
        <span aria-hidden="true">·</span>
        <Metric before="성공 " value={data.runs.success} after="" to="/admin/runs/log?status=성공" />
        <span aria-hidden="true">·</span>
        <Metric before="실패 " value={data.runs.failure} after="" to="/admin/runs/log?status=실패" />
        <span aria-hidden="true">·</span>
        <Metric before="경고 " value={data.runs.warning} after="" to="/admin/runs/log?status=경고" />
      </div>
    </Panel>
  );
  const approvalCard = (
    <Panel key="approvals" title={DASH.approvalsTitle} className={styles.card}>
      <div className={styles.metrics}>
        <Metric before="승인 대기 " value={data.approvals.pending} after="" to="/admin/standards/approvals?result=승인 대기" />
        <span aria-hidden="true">·</span>
        <Metric before="승인 " value={data.approvals.approved} after="" to="/admin/standards/approvals?result=승인" />
        <span aria-hidden="true">·</span>
        <Metric before="돌려받음 " value={data.approvals.returned} after="" to="/admin/standards/approvals?result=돌려받음" />
      </div>
    </Panel>
  );
  const regCard = (
    <Panel key="reg" title={DASH.regTitle} className={styles.card}>
      <div className={styles.metrics}>
        <Metric before="확인할 규정 변경 " value={data.regulations} after="건" to="/admin/standards/regulations" />
      </div>
    </Panel>
  );
  // 기준일 지난 자료가 있으면 자료 카드를, 실패가 있으면 실행 카드를 맨 위로 올린다 (6-3 표시)
  const order = [
    ...(data.data.stale > 0 ? [dataCard] : []),
    ...(data.runs.failure > 0 ? [runCard] : []),
    ...(data.data.stale > 0 ? [] : [dataCard]),
    ...(data.runs.failure > 0 ? [] : [runCard]),
    approvalCard,
    regCard,
  ];

  return (
    <>
      <Panel className={styles.next} aria-label={DASH.runTitle(data.run.name)}>
        <div className={styles.nextHead}>
          <h2 className={styles.nextTitle}>{DASH.runTitle(data.run.name)}</h2>
          <Badge tone={RUN_TONE[data.run.status]}>{data.run.status}</Badge>
        </div>
        {data.next.text ? <p className={styles.task}>{DASH.next(data.next.text)}</p> : null}
        {data.next.to ? (
          <Link to={data.next.to} className={styles.link}>
            {DASH.goto(data.next.toLabel)}
          </Link>
        ) : null}
      </Panel>
      <div className={styles.grid}>{order}</div>
    </>
  );
}
