import { useSearchParams } from 'react-router-dom';
import { listAccess } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import DataTable from '../../components/DataTable.jsx';
import { SelectInput } from '../../components/Field.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import { EmptyState } from '../../components/States.jsx';
import Toolbar from '../../components/Toolbar.jsx';
import { ACCESS } from './copy.js';

/** AD-16 접속 기록 (유형 B): 최신 순. 정기 점검에 쓴다. 고치거나 지울 수 없다. 긴 표라 안에서 스크롤하고 머리 줄을 고정한다. */
export default function AccessPage() {
  const [params, setParams] = useSearchParams();
  const days = params.get('days') || '30';
  const accountId = params.get('account') || '전체';
  const action = params.get('action') || '전체';
  const state = useAsync(() => listAccess({ days, accountId, action }), [days, accountId, action]);

  const setFilter = (key, value, empty) => {
    const next = new URLSearchParams(params);
    if (value === empty) next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  };

  return (
    <div>
      <PageHeader title={ACCESS.title} subtitle={ACCESS.subtitle} />
      <Toolbar>
        <SelectInput label={ACCESS.period} value={days} onChange={(v) => setFilter('days', v, '30')} options={ACCESS.periods} />
        <SelectInput
          label={ACCESS.account}
          value={accountId}
          onChange={(v) => setFilter('account', v, '전체')}
          options={['전체', ...(state.data?.accounts || []).map((a) => a.value)].map((v) => ({
            value: v,
            label: v === '전체' ? '전체' : state.data.accounts.find((a) => a.value === v).label,
          }))}
        />
        <SelectInput label={ACCESS.action} value={action} onChange={(v) => setFilter('action', v, '전체')} options={['전체', ...(state.data?.actions || [])]} />
      </Toolbar>
      <Loadable state={state} areaName={ACCESS.failedArea} rows={8}>
        {(d) => (
          <DataTable
            caption={ACCESS.caption}
            compact
            maxHeight={640}
            columns={[
              { key: 'atLabel', header: ACCESS.head[0], nowrap: true, width: 160 },
              { key: 'who', header: ACCESS.head[1], first: true, width: 300 },
              { key: 'ip', header: ACCESS.head[2], nowrap: true, width: 130 },
              { key: 'action', header: ACCESS.head[3], nowrap: true, width: 140 },
              { key: 'target', header: ACCESS.head[4], width: 360 },
              { key: 'reason', header: ACCESS.head[5], width: 200 },
            ]}
            rows={d.rows}
            getRowKey={(r) => r.key}
            emptyContent={<EmptyState text={ACCESS.empty} />}
          />
        )}
      </Loadable>
    </div>
  );
}
