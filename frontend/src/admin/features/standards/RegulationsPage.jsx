import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listRegulationChanges, markRegulationSeen } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import Badge from '../../components/Badge.jsx';
import Button from '../../components/Button.jsx';
import DataTable from '../../components/DataTable.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import { EmptyState } from '../../components/States.jsx';
import Toolbar from '../../components/Toolbar.jsx';
import { REGS } from './copy.js';
import styles from './Standards.module.css';

/** AD-12 규정 변경 (유형 B): 행을 누르면 바뀐 조문 전후를 펼친다. 펼쳐 본 변경은 '확인한 것'으로 센다. */
export default function RegulationsPage() {
  const navigate = useNavigate();
  const state = useAsync(() => listRegulationChanges(), []);
  const [openId, setOpenId] = useState(null);

  const toggle = (r) => {
    const next = openId === r.id ? null : r.id;
    setOpenId(next);
    if (next && !r.seen) markRegulationSeen({ id: r.id });
  };

  return (
    <div>
      <PageHeader title={REGS.title} subtitle={REGS.subtitle} />
      <Toolbar
        actions={
          <Button variant="secondary" onClick={() => navigate('/admin/standards/dept')}>
            {REGS.toDept}
          </Button>
        }
      />
      <Loadable state={state} areaName={REGS.failedArea} rows={4}>
        {(rows) => (
          <DataTable
            caption={REGS.caption}
            columns={[
              { key: 'kind', header: REGS.head[0], nowrap: true },
              {
                key: 'name',
                header: REGS.head[1],
                first: true,
                render: (r) => (
                  <span className={styles.inlineEdit}>
                    {r.name}
                    {r.pending ? <Badge tone="info">{REGS.pending}</Badge> : null}
                  </span>
                ),
              },
              { key: 'where', header: REGS.head[2] },
              { key: 'date', header: REGS.head[3], nowrap: true },
              { key: 'juris', header: REGS.head[4], render: (r) => r.juris.join(', ') },
            ]}
            rows={rows}
            getRowKey={(r) => r.id}
            expandedKey={openId}
            onRowClick={toggle}
            rowLabel={(r) => `${r.name} 바뀐 조문 ${openId === r.id ? '접기' : '펼치기'}`}
            renderExpanded={(r) => (
              <div className={styles.cmp}>
                <div className={styles.cmpBox}>
                  <p className={styles.cmpTitle}>{REGS.beforeTitle}</p>
                  {r.before}
                </div>
                <div className={styles.cmpBox}>
                  <p className={styles.cmpTitle}>{REGS.afterTitle}</p>
                  {r.after}
                </div>
              </div>
            )}
            emptyContent={<EmptyState text={REGS.empty} />}
          />
        )}
      </Loadable>
    </div>
  );
}
