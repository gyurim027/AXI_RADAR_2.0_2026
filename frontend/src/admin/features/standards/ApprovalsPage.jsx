import { Link, useSearchParams } from 'react-router-dom';
import { listApprovals } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import Badge from '../../components/Badge.jsx';
import DataTable from '../../components/DataTable.jsx';
import { SelectInput } from '../../components/Field.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import { EmptyState } from '../../components/States.jsx';
import Toolbar from '../../components/Toolbar.jsx';
import { APPROVALS } from './copy.js';
import styles from './Standards.module.css';

const RESULT_TONE = { '승인 대기': 'info', 승인: 'success', 반려: 'danger' };

/** 이력 줄에서 가는 곳: 산정 기준은 그 버전의 상세(AD-10), 담당 부서 표는 AD-11 */
function target(r) {
  return r.ref?.kind === 'criteria' ? `/admin/standards/criteria/${r.ref.version}` : '/admin/standards/dept';
}

/** AD-14 승인 이력 (유형 B): 최신 순. 기록은 고치거나 지울 수 없다. 대시보드에서 오면 결과로 거른다. */
export default function ApprovalsPage() {
  const [params, setParams] = useSearchParams();
  const thisYear = new Date().getFullYear();
  const defaultPeriod = `${thisYear}년`;
  const period = params.get('period') || defaultPeriod;
  const result = params.get('result');
  const state = useAsync(() => listApprovals({ period }), [period]);

  const setPeriod = (v) => {
    const next = new URLSearchParams(params);
    if (v === defaultPeriod) next.delete('period');
    else next.set('period', v);
    setParams(next, { replace: true });
  };
  const clearResult = () => {
    const next = new URLSearchParams(params);
    next.delete('result');
    setParams(next, { replace: true });
  };

  return (
    <div>
      <PageHeader title={APPROVALS.title} subtitle={APPROVALS.subtitle} />
      <Toolbar>
        <SelectInput label={APPROVALS.period} value={period} onChange={setPeriod} options={APPROVALS.periods(thisYear)} />
      </Toolbar>
      {result ? (
        <div className={styles.chips}>
          <span className={styles.chip}>
            {APPROVALS.chip(result)}
            <button type="button" className={styles.chipX} onClick={clearResult} aria-label={APPROVALS.chipRemove(result)}>
              ×
            </button>
          </span>
        </div>
      ) : null}
      <Loadable state={state} areaName={APPROVALS.failedArea} rows={5}>
        {(all) => {
          const rows = result ? all.filter((r) => r.result === result) : all;
          return (
            <DataTable
              caption={APPROVALS.caption}
              columns={[
                {
                  key: 'target',
                  header: APPROVALS.head[0],
                  first: true,
                  nowrap: true,
                  // 담당 부서 표 제안은 버전이 없어 대상 이름에 링크를 건다
                  render: (r) =>
                    r.ref?.kind === 'dept' ? (
                      <Link to={target(r)} className={styles.back} style={{ marginBottom: 0 }}>
                        {r.target}
                      </Link>
                    ) : (
                      r.target
                    ),
                },
                {
                  key: 'version',
                  header: APPROVALS.head[1],
                  nowrap: true,
                  render: (r) =>
                    r.ref?.kind === 'criteria' ? (
                      <Link to={target(r)} className={styles.back} style={{ marginBottom: 0 }}>
                        {r.version}
                      </Link>
                    ) : (
                      r.version
                    ),
                },
                { key: 'proposer', header: APPROVALS.head[2] },
                { key: 'at', header: APPROVALS.head[3], nowrap: true, render: (r) => String(r.at).slice(0, 10).replaceAll('-', '.') },
                { key: 'approver', header: APPROVALS.head[4] },
                { key: 'result', header: APPROVALS.head[5], nowrap: true, render: (r) => <Badge tone={RESULT_TONE[r.result]}>{r.result}</Badge> },
                {
                  key: 'reason',
                  header: APPROVALS.head[6],
                  render: (r) => (
                    <span>
                      {r.reason}
                      {r.result === '반려' ? (
                        <>
                          {' '}
                          <Link to={target(r)} className={styles.back} style={{ marginBottom: 0 }}>
                            {APPROVALS.fix}
                          </Link>
                        </>
                      ) : null}
                    </span>
                  ),
                },
              ]}
              rows={rows}
              getRowKey={(r) => r.id}
              emptyContent={<EmptyState text={APPROVALS.empty} actionLabel={result ? APPROVALS.emptyClear : undefined} onAction={clearResult} />}
            />
          );
        }}
      </Loadable>
    </div>
  );
}
