import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { listData } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import Badge from '../../components/Badge.jsx';
import Button from '../../components/Button.jsx';
import DataTable from '../../components/DataTable.jsx';
import { SelectInput } from '../../components/Field.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import { EmptyState } from '../../components/States.jsx';
import Toolbar from '../../components/Toolbar.jsx';
import { LIST } from './copy.js';
import styles from './Data.module.css';

const FRESH_TONE = { 최신: 'success', '갱신 예정일 지남': 'warning', 빠짐: 'danger' };

/** AD-02 데이터 목록 (유형 B). 갱신 예정일 지남과 빠짐을 맨 위에 둔다. 행을 누르면 회차별 원본 목록이 펼쳐진다. */
export default function DataListPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const freshness = params.get('freshness') || '전체';
  const source = params.get('source') || '전체';
  const [openId, setOpenId] = useState(null);
  const state = useAsync(() => listData({ freshness, source }), [freshness, source]);

  const setFilter = (key, value) => {
    const next = new URLSearchParams(params);
    if (value === '전체') next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
    setOpenId(null);
  };
  const clearFilters = () => {
    setParams({}, { replace: true });
    setOpenId(null);
  };

  const columns = [
    { key: 'id', header: LIST.head[0], first: true, nowrap: true, width: 120 },
    { key: 'name', header: LIST.head[1], width: 260, render: (d) => <span className={styles.name}>{d.name}</span> },
    { key: 'org', header: LIST.head[2], width: 170 },
    { key: 'source', header: LIST.head[3], nowrap: true, width: 170 },
    {
      key: 'cycle',
      header: LIST.head[4],
      nowrap: true,
      width: 150,
      render: (d) => (d.cycle === '1회성' ? <span className={styles.stack}>{d.cycle} <Badge tone="neutral">{LIST.past}</Badge></span> : d.cycle || '-'),
    },
    {
      key: 'basis',
      header: LIST.head[5],
      nowrap: true,
      width: 160,
      render: (d) => (d.basis ? d.basis : <Badge tone="warning">{LIST.basisMissing}</Badge>),
    },
    { key: 'collectedAt', header: LIST.head[6], nowrap: true, width: 110, render: (d) => d.collectedAt || '-' },
    { key: 'official', header: LIST.head[7], nowrap: true, width: 140 },
    { key: 'freshness', header: LIST.head[8], nowrap: true, width: 170, render: (d) => <Badge tone={FRESH_TONE[d.freshness]}>{d.freshness}</Badge> },
    { key: 'share', header: LIST.head[9], width: 250 },
    { key: 'ai', header: LIST.head[10], nowrap: true, width: 150 },
  ];

  return (
    <div>
      <PageHeader title={LIST.title} subtitle={LIST.subtitle} />
      <Toolbar
        actions={
          <Button variant="primary" onClick={() => navigate('/admin/data/upload')}>
            {LIST.upload}
          </Button>
        }
      >
        <SelectInput label={LIST.freshnessLabel} value={freshness} onChange={(v) => setFilter('freshness', v)} options={LIST.freshnessOptions} />
        <SelectInput label={LIST.sourceLabel} value={source} onChange={(v) => setFilter('source', v)} options={LIST.sourceOptions} />
      </Toolbar>
      <p className={styles.helpLine}>{LIST.help}</p>
      <Loadable state={state} areaName={LIST.failedArea} rows={8}>
        {(rows) => (
          <DataTable
            caption={LIST.caption}
            columns={columns}
            rows={rows}
            getRowKey={(d) => d.id}
            onRowClick={(d) => d.files.length > 0 && setOpenId(openId === d.id ? null : d.id)}
            canExpand={(d) => d.files.length > 0}
            expandedKey={openId}
            renderExpanded={(d) => <Versions item={d} />}
            rowLabel={(d) => `${d.name} 회차별 원본 목록 ${openId === d.id ? '접기' : '펼치기'}`}
            emptyContent={<EmptyState text={LIST.empty} actionLabel={LIST.emptyClear} onAction={clearFilters} />}
          />
        )}
      </Loadable>
    </div>
  );
}

/** 회차별 원본 목록. 올린 날과 올린 운영자는 파일로 올린 자료만 보인다. */
function Versions({ item }) {
  return (
    <table className={styles.versions}>
      <thead>
        <tr>
          {LIST.versionHead.map((h) => (
            <th key={h} scope="col">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {item.files.map((f) => (
          <tr key={`${f.run}-${f.at}-${f.file}`}>
            <td>{f.run}</td>
            <td>{f.at.replaceAll('-', '.')}</td>
            <td>{f.by}</td>
            <td className={styles.file}>{f.file}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
