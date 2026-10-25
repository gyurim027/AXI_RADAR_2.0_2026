import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { listRegulationChanges, markRegulationSeen } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import Badge from '../../components/Badge.jsx';
import Button from '../../components/Button.jsx';
import DataTable from '../../components/DataTable.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import { EmptyState } from '../../components/States.jsx';
import Toolbar from '../../components/Toolbar.jsx';
import { reportActionError } from '../../utils/actionError.js';
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
    if (next && !r.seen) markRegulationSeen({ id: r.id }).catch(reportActionError);
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
              { key: 'juris', header: REGS.head[4], nowrap: true, render: (r) => REGS.jurCount(r.juris.length) },
            ]}
            rows={rows}
            getRowKey={(r) => r.id}
            expandedKey={openId}
            onRowClick={toggle}
            rowLabel={(r) => `${r.name} 바뀐 조문 ${openId === r.id ? '접기' : '펼치기'}`}
            renderExpanded={(r) => (
              <div>
                <p className={styles.detected}>{REGS.detected(r.detected || '-')}</p>
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
                <table className={styles.jurTable}>
                  <caption className="sr-only">{REGS.jurCount(r.juris.length)}</caption>
                  <thead>
                    <tr>
                      {REGS.jurHead.map((h) => (
                        <th key={h} scope="col">
                          {h}
                        </th>
                      ))}
                      <th scope="col">
                        <span className="sr-only">이동</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {r.jurRows.map((j) => (
                      <tr key={j.id}>
                        <td>{j.id}</td>
                        <td>{j.problem}</td>
                        <td>{j.dept}</td>
                        <td>
                          <Link to="/admin/standards/dept" className={styles.jurLink} aria-label={`${j.id} ${REGS.toDeptRow}`}>
                            {REGS.toDeptRow}
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            emptyContent={<EmptyState text={REGS.empty} />}
          />
        )}
      </Loadable>
    </div>
  );
}
