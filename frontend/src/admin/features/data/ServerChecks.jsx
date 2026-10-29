import { useState } from 'react';
import { getUnlocated, listLowComplaints } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
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

/**
 * AD-04 검사 결과, 서버 모드. 위치 미확인 탭(좌표 확보 현황·단속장소 상위 곳)과 낮음 민원 창만 서버에 연결했다.
 * 나머지 탭(형식 오류·확인이 필요한 값·시설 묶음 실패)은 검사 결과 목록 API(/api/data-issues)가 생기면 연결한다.
 */
export default function ServerChecks() {
  const [tab, setTab] = useState('location');
  return (
    <div>
      <PageHeader title={CHECKS.title} subtitle={CHECKS.subtitle} />
      <div className={styles.stackPanels}>
        <Tabs label={CHECKS.title} idPrefix="checks" value={tab} onChange={setTab} tabs={KEYS.map((k) => ({ key: k, label: CHECKS.tabs[k] }))} />
        <div id="checks-panel" role="tabpanel" aria-labelledby={`checks-${tab}`} className={styles.stackPanels}>
          {tab === 'location' ? <LocationTab /> : <EmptyState text={CHECKS.tabNotConnected} />}
        </div>
      </div>
    </div>
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
