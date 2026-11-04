import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getChecks, listLowLocation } from '../../../api/admin.js';
import { opsBackendEnabled } from '../../../api/backend.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import Button from '../../components/Button.jsx';
import DataTable from '../../components/DataTable.jsx';
import Dialog from '../../components/Dialog.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Panel from '../../components/Panel.jsx';
import { EmptyState } from '../../components/States.jsx';
import Tabs from '../../components/Tabs.jsx';
import ServerChecks from './ServerChecks.jsx';
import { CHECKS } from './copy.js';
import styles from './Data.module.css';

const KEYS = ['format', 'value', 'location', 'group'];

/** AD-04 검사 결과. 서버 모드에서는 서버에 연결된 부분(위치 미확인·낮음 민원)만 보인다. */
export default function ChecksPage() {
  return opsBackendEnabled ? <ServerChecks /> : <MockChecksPage />;
}

/** AD-04 검사 결과 (유형 B): 탭 + 표. 자동으로 고치거나 지우지 않는다. 같은 데이터를 고른 채로 업로드를 연다. */
function MockChecksPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState('format');
  const [lowOpen, setLowOpen] = useState(false);
  const state = useAsync(() => getChecks(), []);

  return (
    <div>
      <PageHeader title={CHECKS.title} subtitle={CHECKS.subtitle} />
      <Loadable state={state} areaName={CHECKS.failedArea} rows={6}>
        {(d) => (
          <div className={styles.stackPanels}>
            <Tabs
              label={CHECKS.title}
              idPrefix="checks"
              value={tab}
              onChange={setTab}
              tabs={KEYS.map((k) => ({ key: k, label: CHECKS.tabs[k], count: d[k].length }))}
            />
            <div id="checks-panel" role="tabpanel" aria-labelledby={`checks-${tab}`} className={styles.stackPanels}>
              {tab === 'location' ? (
                <Panel>
                  <p className={styles.lowLine}>
                    {CHECKS.lowBefore}
                    <button type="button" className={styles.lowBtn} onClick={() => setLowOpen(true)} aria-haspopup="dialog">
                      {d.low.count}
                    </button>
                    {CHECKS.lowAfter(d.low.topCells, d.low.changedCells)}
                  </p>
                  <p className={styles.note}>{CHECKS.lowNote}</p>
                </Panel>
              ) : null}
              <DataTable
                caption={CHECKS.tabs[tab]}
                columns={[
                  { key: 'data', header: CHECKS.head[0], first: true },
                  { key: 'row', header: CHECKS.head[1], align: 'right', nowrap: true },
                  { key: 'kind', header: CHECKS.head[2], nowrap: true },
                  { key: 'reason', header: CHECKS.head[3] },
                  {
                    key: 'action',
                    header: <span className="sr-only">동작</span>,
                    align: 'right',
                    render: (r) => (
                      <Button variant="text" onClick={() => navigate(`/admin/data/upload?data=${r.dataId}`)} aria-label={`${r.data} ${r.row}행 ${CHECKS.reupload}`}>
                        {CHECKS.reupload}
                      </Button>
                    ),
                  },
                ]}
                rows={d[tab]}
                getRowKey={(r) => r.id}
                emptyContent={<EmptyState text={CHECKS.empty} />}
              />
            </div>
            {lowOpen ? <LowDialog onClose={() => setLowOpen(false)} /> : null}
          </div>
        )}
      </Loadable>
    </div>
  );
}

function LowDialog({ onClose }) {
  const state = useAsync(() => listLowLocation(), []);
  return (
    <Dialog title={CHECKS.lowTitle} titleId="low-title" size="md" onClose={onClose} closeLabel={CHECKS.lowClose}>
      <Loadable state={state} areaName={CHECKS.lowTitle} rows={4}>
        {(rows) => (
          <DataTable
            caption={CHECKS.lowTitle}
            compact
            maxHeight={360}
            columns={[
              { key: 'row', header: CHECKS.head[1], align: 'right', nowrap: true },
              { key: 'kind', header: CHECKS.head[2], nowrap: true },
              { key: 'reason', header: CHECKS.head[3] },
            ]}
            rows={rows}
            getRowKey={(r) => r.id}
          />
        )}
      </Loadable>
    </Dialog>
  );
}
