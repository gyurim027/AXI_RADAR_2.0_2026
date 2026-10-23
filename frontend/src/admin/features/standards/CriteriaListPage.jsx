import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { createVersion, listVersions } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import Badge from '../../components/Badge.jsx';
import Button from '../../components/Button.jsx';
import DataTable from '../../components/DataTable.jsx';
import { SelectInput } from '../../components/Field.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Toolbar from '../../components/Toolbar.jsx';
import { CRITERIA } from './copy.js';
import styles from './Standards.module.css';

export const VERSION_TONE = { '작성 중': 'neutral', '승인 대기': 'warning', 승인됨: 'success', 돌려받음: 'danger' };

/** AD-09 산정 기준 목록 (유형 B): 쪽 넘김 없이 한 표. 행을 누르면 상세로 간다. 새 버전은 지금 승인된 버전을 복사해 만든다. */
export default function CriteriaListPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const status = params.get('status') || '전체';
  const state = useAsync(() => listVersions({ status }), [status]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const create = async () => {
    setBusy(true);
    setError('');
    try {
      const r = await createVersion();
      navigate(`/admin/standards/criteria/${r.version}`);
    } catch {
      setError(CRITERIA.createFailed);
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader title={CRITERIA.title} subtitle={CRITERIA.subtitle} />
      <Toolbar
        actions={
          <Button variant="primary" loading={busy} onClick={create}>
            {CRITERIA.create}
          </Button>
        }
      >
        <SelectInput
          label={CRITERIA.statusLabel}
          value={status}
          onChange={(v) => setParams(v === '전체' ? {} : { status: v }, { replace: true })}
          options={CRITERIA.statuses}
        />
      </Toolbar>
      {error ? (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      ) : null}
      <Loadable state={state} areaName={CRITERIA.failedArea} rows={4}>
        {(rows) => (
          <DataTable
            caption={CRITERIA.caption}
            columns={[
              { key: 'version', header: CRITERIA.head[0], first: true, nowrap: true },
              { key: 'name', header: CRITERIA.head[1] },
              { key: 'run', header: CRITERIA.head[2], nowrap: true },
              { key: 'status', header: CRITERIA.head[3], nowrap: true, render: (v) => <Badge tone={VERSION_TONE[v.status]}>{v.status}</Badge> },
              { key: 'updated', header: CRITERIA.head[4], nowrap: true },
              { key: 'indicatorCount', header: CRITERIA.head[5], align: 'right' },
            ]}
            rows={rows}
            getRowKey={(v) => v.version}
            onRowClick={(v) => navigate(`/admin/standards/criteria/${v.version}`)}
            rowLabel={(v) => `산정 기준 ${v.version} 상세 보기`}
          />
        )}
      </Loadable>
    </div>
  );
}
