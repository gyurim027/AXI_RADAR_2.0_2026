import { Link } from 'react-router-dom';
import { getDashboard } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import { opsBackendEnabled } from '../../../api/backend.js';
import { useAdminOptional } from '../../AdminProvider.jsx';
import { isOpenInServerMode } from '../../serverRoutes.js';
import Badge, { RUN_TONE } from '../../components/Badge.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Panel from '../../components/Panel.jsx';
import { ErrorState, SkeletonRows } from '../../components/States.jsx';
import { DASH } from './copy.js';
import styles from './Dashboard.module.css';

/** 서버 연결 모드에서는 아직 연결하지 않은 화면으로 가는 링크를 걸지 않는다 (열리지 않고 첫 화면으로 돌아오기 때문). */
const linkTo = (to) => (!opsBackendEnabled || isOpenInServerMode(to) ? to : null);
/** 서버가 모르는 칸은 null로 온다. 0과 구분해 '-'로 보인다. */
const known = (v) => v !== null && v !== undefined;
const show = (v) => (known(v) ? v : '-');

/** 숫자를 누르면 그 상태로 거른 화면으로 간다. 숫자는 크게, 앞뒤 글자는 그대로 읽힌다. */
function Metric({ before, value, after, to }) {
  const inner = (
    <>
      {before}
      <span className={styles.value}>{show(value)}</span>
      {after}
    </>
  );
  const target = linkTo(to);
  return target ? (
    <Link to={target} className={styles.metric}>
      {inner}
    </Link>
  ) : (
    <span className={styles.metric}>{inner}</span>
  );
}

/** 카드 하나: 오른쪽 위에 상태 배지, 아래에 '보러 가기' 링크 (A-1). 숫자만 있던 카드가 어디로 가는지 드러낸다. */
function StatCard({ title, tone, state, to, more, children }) {
  return (
    <Panel title={title} className={styles.card} actions={<Badge tone={tone}>{state}</Badge>}>
      {children}
      {linkTo(to) ? (
        <Link to={linkTo(to)} className={styles.more}>
          {more}
        </Link>
      ) : null}
    </Panel>
  );
}

/** AD-01 대시보드 (유형 A): 맨 위 폭 전체 '다음 할 일' 카드 아래에 카드 격자. 기준일 지난 자료가 있으면 자료 카드를, 실패가 있으면 실행 카드를 맨 위로 올린다. */
export default function DashboardPage() {
  // 서버 연결 모드에는 회차 선택이 없다. 서버가 가장 최근 회차를 알려 준다.
  const runId = useAdminOptional()?.run?.id;
  const { data, failed, showSkeleton, reload } = useAsync(() => getDashboard({ runId }), [runId]);

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
  const dataKnown = known(data.data.stale) || known(data.data.missing);
  const dataBad = data.data.stale > 0 || data.data.missing > 0;
  const runCount = data.runs.success + data.runs.failure + data.runs.warning;
  const dataCard = (
    <StatCard key="data" title={DASH.dataTitle} tone={!dataKnown ? 'neutral' : dataBad ? 'warning' : 'success'} state={!dataKnown ? DASH.state.unknown : dataBad ? DASH.state.check : DASH.state.ok} to="/admin/data/list" more={DASH.more.data}>
      <div className={styles.metrics}>
        <Metric before="기준일 지난 자료 " value={data.data.stale} after="종" to="/admin/data/list?freshness=갱신 예정일 지남" />
        <span aria-hidden="true">·</span>
        <Metric before="빠진 자료 " value={data.data.missing} after="종" to="/admin/data/list?freshness=빠짐" />
      </div>
    </StatCard>
  );
  const runCard = (
    <StatCard
      key="runs"
      title={DASH.runsTitle}
      tone={data.runs.failure > 0 ? 'danger' : data.runs.warning > 0 ? 'warning' : 'success'}
      state={data.runs.failure > 0 ? DASH.state.fail : data.runs.warning > 0 ? DASH.state.check : DASH.state.ok}
      to="/admin/runs/log"
      more={DASH.more.runs}
    >
      {runCount === 0 ? (
        <p className={styles.empty}>{DASH.runsEmpty}</p>
      ) : (
        <div className={styles.metrics}>
          <span>{`최근 ${data.runs.days}일`}</span>
          <span aria-hidden="true">·</span>
          <Metric before="성공 " value={data.runs.success} after="" to="/admin/runs/log?status=성공" />
          <span aria-hidden="true">·</span>
          <Metric before="실패 " value={data.runs.failure} after="" to="/admin/runs/log?status=실패" />
          <span aria-hidden="true">·</span>
          <Metric before="경고 " value={data.runs.warning} after="" to="/admin/runs/log?status=경고" />
        </div>
      )}
    </StatCard>
  );
  const approvalCard = (
    <StatCard key="approvals" title={DASH.approvalsTitle} tone={data.approvals?.pending > 0 ? 'info' : 'neutral'} state={!data.approvals ? DASH.state.unknown : data.approvals.pending > 0 ? DASH.state.wait : DASH.state.none} to="/admin/standards/approvals" more={DASH.more.approvals}>
      <div className={styles.metrics}>
        <Metric before="승인 대기 " value={data.approvals?.pending} after="" to="/admin/standards/approvals?result=승인 대기" />
        <span aria-hidden="true">·</span>
        <Metric before="승인 " value={data.approvals?.approved} after="" to="/admin/standards/approvals?result=승인" />
        <span aria-hidden="true">·</span>
        <Metric before="돌려받음 " value={data.approvals?.returned} after="" to="/admin/standards/approvals?result=돌려받음" />
      </div>
    </StatCard>
  );
  const regCard = (
    <StatCard key="reg" title={DASH.regTitle} tone={!known(data.regulations) ? 'neutral' : data.regulations > 0 ? 'warning' : 'success'} state={!known(data.regulations) ? DASH.state.unknown : data.regulations > 0 ? DASH.state.check : DASH.state.ok} to="/admin/standards/regulations" more={DASH.more.regs}>
      <div className={styles.metrics}>
        <Metric before="확인할 규정 변경 " value={data.regulations} after="건" to="/admin/standards/regulations" />
      </div>
    </StatCard>
  );
  // 링크는 승인 대기 버전 상세로, 없으면 지금 쓰는 버전 상세로 간다 (AD-01 6-1)
  // 서버는 버전 하나만 준다: 승인 대기가 있으면 그 버전, 없으면 지금 쓰는 버전 (label이 있으면 서버 모양)
  const c = data.criteria;
  const fromServer = Boolean(c && 'label' in c);
  const criteriaPending = fromServer ? c.pending : c?.pending;
  const criteriaTarget = fromServer ? c.id : c?.pending || c?.approved;
  const criteriaCard = (
    <StatCard
      key="criteria"
      title={DASH.criteriaTitle}
      tone={criteriaPending ? 'info' : 'neutral'}
      state={!c ? DASH.state.unknown : criteriaPending ? DASH.state.wait : DASH.state.current}
      to={criteriaTarget ? `/admin/standards/criteria/${criteriaTarget}` : '/admin/standards/criteria'}
      more={DASH.more.criteria}
    >
      <div className={styles.metrics}>
        <span>{fromServer ? DASH.criteriaOne(c.label, c.pending, c.at) : DASH.criteriaLine(c?.approved, c?.pending)}</span>
      </div>
    </StatCard>
  );
  // 검사 결과 카드는 서버가 줄 때만: 고칠 자료는 '다음에 할 일'과 같은 기준, 이상한 값·같은 시설 의심은 고치지 않고 표시만 한다
  const checksCard = data.checks ? (
    <StatCard key="checks" title={DASH.checksTitle} tone={data.checks.fix > 0 ? 'warning' : 'neutral'} state={!known(data.checks.fix) ? DASH.state.unknown : data.checks.fix > 0 ? DASH.state.check : DASH.state.ok} to="/admin/data/checks" more={DASH.more.checks}>
      <div className={styles.metrics}>
        <Metric before="고칠 자료 " value={data.checks.fix} after="건" to="/admin/data/checks" />
        <span aria-hidden="true">·</span>
        <Metric before="확인 필요(참고) " value={data.checks.reference} after="건" to="/admin/data/checks" />
      </div>
    </StatCard>
  ) : null;
  // 기준일 지난 자료가 있으면 자료 카드를, 실패가 있으면 실행 카드를 맨 위로 올린다 (6-3 표시)
  const order = [
    ...(data.data.stale > 0 ? [dataCard] : []),
    ...(data.runs.failure > 0 ? [runCard] : []),
    ...(data.data.stale > 0 ? [] : [dataCard]),
    ...(data.runs.failure > 0 ? [] : [runCard]),
    ...(checksCard ? [checksCard] : []),
    criteriaCard,
    approvalCard,
    regCard,
  ];

  return (
    <>
      <Panel className={styles.next} aria-label={DASH.runTitle(data.run.name)}>
        <div className={styles.nextHead}>
          <h2 className={styles.nextTitle}>{DASH.runTitle(data.run.name)}</h2>
          <Badge tone={RUN_TONE[data.run.status]}>{data.run.status || '-'}</Badge>
        </div>
        {data.next.text ? <p className={styles.task}>{DASH.next(data.next.text)}</p> : null}
        {linkTo(data.next.to) ? (
          <Link to={data.next.to} className={styles.link}>
            {DASH.goto(data.next.toLabel)}
          </Link>
        ) : null}
      </Panel>
      <div className={styles.grid}>{order}</div>
    </>
  );
}
