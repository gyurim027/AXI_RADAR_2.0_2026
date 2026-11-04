import { useState } from 'react';
import { getUnlocated, listIssues, listLowComplaints } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import Button from '../../components/Button.jsx';
import DataTable from '../../components/DataTable.jsx';
import Dialog from '../../components/Dialog.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Panel from '../../components/Panel.jsx';
import { EmptyState } from '../../components/States.jsx';
import Tabs from '../../components/Tabs.jsx';
import { CHECKS } from './copy.js';
import styles from './Data.module.css';

const KEYS = ['format', 'value', 'location', 'group'];
const num = (n) => (n == null ? '-' : Number(n).toLocaleString('ko-KR'));

// 탭 → 검사 종류. A-05 형식·빈칸·중복, A-06 이상한 값, A-08 같은 시설 묶기.
const CHECK_FN = { format: 'A-05', value: 'A-06', group: 'A-08' };

/**
 * AD-04 검사 결과, 서버 모드. 위치 미확인 탭(좌표 확보 현황·단속장소 상위 곳)과 낮음 민원 창,
 * 그리고 검사 결과 목록(/api/data-issues)으로 형식 오류·확인이 필요한 값·시설 묶음 실패 탭을 보인다.
 * 서버가 검사 종류로만 거를 수 있어, 사본(중복 행)은 형식 오류 탭에 '확인 필요(참고)'로 같이 보인다.
 */
export default function ServerChecks() {
  const [tab, setTab] = useState('format');
  // 탭 이름 옆 숫자: 세 종류의 전체 건수를 한 번에 받아 둔다.
  const counts = useAsync(
    () => Promise.all(Object.values(CHECK_FN).map((fn) => listIssues({ checkFn: fn, limit: 1 }))),
    [],
  );
  const total = (k) => (counts.data ? counts.data[Object.keys(CHECK_FN).indexOf(k)]?.total : undefined);
  return (
    <div>
      <PageHeader title={CHECKS.title} subtitle={CHECKS.subtitle} />
      <div className={styles.stackPanels}>
        <Tabs label={CHECKS.title} idPrefix="checks" value={tab} onChange={setTab} tabs={KEYS.map((k) => ({ key: k, label: CHECKS.tabs[k], count: total(k) }))} />
        <div id="checks-panel" role="tabpanel" aria-labelledby={`checks-${tab}`} className={styles.stackPanels}>
          {tab === 'location' ? <LocationTab /> : <IssueTab key={tab} tabKey={tab} />}
        </div>
      </div>
    </div>
  );
}

const PAGE = 50;

/** 검사 결과 목록 한 탭. 처음 PAGE건을 보이고 '더 불러오기'로 다음 쪽을 이어 붙인다. */
function IssueTab({ tabKey }) {
  const checkFn = CHECK_FN[tabKey];
  const first = useAsync(() => listIssues({ checkFn, limit: PAGE }), [checkFn]);
  return (
    <Loadable state={first} areaName={CHECKS.tabs[tabKey]} rows={5}>
      {(d) => <IssueTable tabKey={tabKey} first={d} />}
    </Loadable>
  );
}

function IssueTable({ tabKey, first }) {
  const checkFn = CHECK_FN[tabKey];
  const [extra, setExtra] = useState([]);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const rows = [...first.rows, ...extra];
  const loadMore = () => {
    setBusy(true);
    setFailed(false);
    listIssues({ checkFn, limit: PAGE, offset: rows.length })
      .then((d) => setExtra((prev) => [...prev, ...d.rows]))
      .catch(() => setFailed(true))
      .finally(() => setBusy(false));
  };
  const withLabel = checkFn === 'A-05';
  const columns = [
    { key: 'table', header: CHECKS.issueHead[0], first: true, render: (r) => r.table || '-' },
    { key: 'row', header: CHECKS.issueHead[1], align: 'right', nowrap: true, render: (r) => r.row ?? r.rowKey ?? '-' },
    { key: 'kind', header: CHECKS.issueHead[2], nowrap: true, render: (r) => r.kind || '-' },
    { key: 'reason', header: CHECKS.issueHead[3], render: (r) => r.reason || '-' },
    ...(withLabel
      ? [
          { key: 'label', header: CHECKS.issueLabelHead, nowrap: true, render: (r) => r.label || '-' },
          { key: 'role', header: CHECKS.issueRoleHead, nowrap: true, render: (r) => r.role || '-' },
        ]
      : []),
  ];
  return (
    <Panel padded={false}>
      <DataTable
        caption={CHECKS.tabs[tabKey]}
        compact
        columns={columns}
        rows={rows}
        getRowKey={(r) => r.id}
        emptyContent={<EmptyState text={CHECKS.empty} />}
      />
      <p className={styles.panelFoot}>{CHECKS.issueFoot(num(rows.length), num(first.total))}</p>
      {failed ? <p className={styles.panelFoot} role="alert">{CHECKS.issueMoreFailed}</p> : null}
      {rows.length < first.total ? (
        <div className={styles.panelFoot}>
          <Button variant="secondary" loading={busy} onClick={loadMore}>{CHECKS.issueMore}</Button>
        </div>
      ) : null}
    </Panel>
  );
}

function LocationTab() {
  const [lowOpen, setLowOpen] = useState(false);
  const unlocated = useAsync(() => getUnlocated({ limit: 20 }), []);
  // 낮음 민원은 볼 때마다 접근 기록이 남는다. 건수와 창 목록이 한 번의 요청을 같이 쓴다.
  const low = useAsync(() => listLowComplaints({ limit: 1000 }), []);
  return (
    <>
      <Panel>
        <Loadable state={low} areaName={CHECKS.lowTitle} rows={1}>
          {(d) => (
            <>
              <p className={styles.lowLine}>
                {CHECKS.lowBefore}
                <button type="button" className={styles.lowBtn} onClick={() => setLowOpen(true)} aria-haspopup="dialog">
                  {num(d.total)}
                </button>
                {CHECKS.lowUnit}
              </p>
              <p className={styles.note}>{CHECKS.lowNoteServer}</p>
              {lowOpen ? <LowDialog data={d} onClose={() => setLowOpen(false)} /> : null}
            </>
          )}
        </Loadable>
      </Panel>
      <Loadable state={unlocated} areaName={CHECKS.coverageTitle} rows={5}>
        {(d) => (
          <>
            <Panel title={CHECKS.coverageTitle} padded={false}>
              <DataTable
                caption={CHECKS.coverageCaption}
                columns={[
                  { key: 'label', header: CHECKS.coverageHead[0], first: true },
                  { key: 'totalRows', header: CHECKS.coverageHead[1], align: 'right', nowrap: true, render: (r) => num(r.totalRows) },
                  { key: 'missingRows', header: CHECKS.coverageHead[2], align: 'right', nowrap: true, render: (r) => num(r.missingRows) },
                  { key: 'missingRate', header: CHECKS.coverageHead[3], align: 'right', nowrap: true, render: (r) => (r.missingRate == null ? '-' : `${r.missingRate}%`) },
                ]}
                rows={d.coverage || []}
                getRowKey={(r) => r.table}
              />
            </Panel>
            <Panel title={CHECKS.topTitle} description={CHECKS.topNote} padded={false}>
              <DataTable
                caption={CHECKS.topCaption}
                compact
                columns={[
                  { key: 'name', header: CHECKS.topHead[0], first: true },
                  { key: 'enforceCnt', header: CHECKS.topHead[1], align: 'right', nowrap: true, render: (r) => num(r.enforceCnt) },
                ]}
                rows={d.top?.items || []}
                getRowKey={(r) => r.rowKey}
                emptyContent={<EmptyState text={CHECKS.empty} />}
              />
              <p className={styles.panelFoot}>{CHECKS.topFoot(num(d.top?.totalMissing), (d.top?.items || []).length)}</p>
            </Panel>
          </>
        )}
      </Loadable>
    </>
  );
}

/** 낮음 민원 창: 접수일·구·동·찾은 방법만 보인다. 신고에 적힌 위치 글자와 좌표는 보이지 않는다. */
function LowDialog({ data, onClose }) {
  return (
    <Dialog title={CHECKS.lowTitle} titleId="low-title" size="md" onClose={onClose} closeLabel={CHECKS.lowClose}>
      <DataTable
        caption={CHECKS.lowTitle}
        compact
        maxHeight={360}
        columns={[
          { key: 'date', header: CHECKS.lowHead[0], nowrap: true, render: (r) => r.date || '-' },
          { key: 'gu', header: CHECKS.lowHead[1], nowrap: true, render: (r) => r.gu || '-' },
          { key: 'dong', header: CHECKS.lowHead[2], nowrap: true, render: (r) => r.dong || '-' },
          { key: 'method', header: CHECKS.lowHead[3], render: (r) => r.method || '-' },
        ]}
        rows={data.rows}
        getRowKey={(r) => r.id}
      />
      {data.total > data.rows.length ? <p className={styles.note}>{CHECKS.lowPartial(num(data.rows.length), num(data.total))}</p> : null}
    </Dialog>
  );
}
