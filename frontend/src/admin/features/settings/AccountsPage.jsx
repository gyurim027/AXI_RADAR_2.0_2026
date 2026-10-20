import { useState } from 'react';
import { createAccount, listAccounts, setAccountStatus } from '../../../api/admin.js';
import { useAuth } from '../../../app/providers/AuthProvider.jsx';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import Badge from '../../components/Badge.jsx';
import Button from '../../components/Button.jsx';
import DataTable from '../../components/DataTable.jsx';
import Dialog from '../../components/Dialog.jsx';
import { SelectInput, TextInput } from '../../components/Field.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Panel, { Banner } from '../../components/Panel.jsx';
import { GU_LIST } from '../../../shared/constants.js';
import { ACCOUNTS } from './copy.js';
import styles from './Settings.module.css';
import { reportActionError } from '../../utils/actionError.js';

/** AD-15 계정 (유형 B + E): 계정을 만들고 역할을 준다. 지우지 않고 멈추거나 다시 쓴다. 권한을 주고 바꾸고 거둔 기록을 남긴다. */
export default function AccountsPage() {
  const { user } = useAuth();
  const state = useAsync(() => listAccounts(), []);
  const [creating, setCreating] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState(null);

  const toggle = async (row) => {
    setBusyId(row.id);
    setError('');
    try {
      await setAccountStatus({ id: row.id, status: row.status === ACCOUNTS.statusOn ? '멈춤' : '사용 중' });
      setDone(false);
      state.reload();
    } catch {
      setError(ACCOUNTS.actionFailed);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div>
      <PageHeader title={ACCOUNTS.title} subtitle={ACCOUNTS.subtitle}>
        <Button variant="primary" onClick={() => setCreating(true)}>
          {ACCOUNTS.create}
        </Button>
      </PageHeader>
      <div className={styles.stack}>
        {done ? <Banner tone="success">{ACCOUNTS.done}</Banner> : null}
        {error ? <Banner tone="danger">{error}</Banner> : null}
        <Loadable state={state} areaName={ACCOUNTS.failedArea} rows={6}>
          {(d) => (
            <>
              <DataTable
                caption={ACCOUNTS.caption}
                columns={[
                  { key: 'name', header: ACCOUNTS.head[0], first: true, nowrap: true },
                  { key: 'id', header: ACCOUNTS.head[1], nowrap: true },
                  { key: 'role', header: ACCOUNTS.head[2], nowrap: true },
                  { key: 'gu', header: ACCOUNTS.head[3], nowrap: true },
                  { key: 'team', header: ACCOUNTS.head[4], nowrap: true },
                  { key: 'status', header: ACCOUNTS.head[5], nowrap: true, render: (r) => <Badge tone={r.status === ACCOUNTS.statusOn ? 'success' : 'neutral'}>{r.status === '멈춤' ? ACCOUNTS.statusOff : ACCOUNTS.statusOn}</Badge> },
                  { key: 'last', header: ACCOUNTS.head[6], nowrap: true },
                  {
                    key: 'action',
                    header: <span className="sr-only">동작</span>,
                    align: 'right',
                    render: (r) =>
                      r.id === user.id ? null : (
                        <Button compact variant="secondary" loading={busyId === r.id} onClick={() => toggle(r)} aria-label={`${r.name} ${r.status === ACCOUNTS.statusOn ? ACCOUNTS.stop : ACCOUNTS.resume}`}>
                          {r.status === ACCOUNTS.statusOn ? ACCOUNTS.stop : ACCOUNTS.resume}
                        </Button>
                      ),
                  },
                ]}
                rows={d.rows}
                getRowKey={(r) => r.id}
              />
              <Panel title={ACCOUNTS.logTitle}>
                <ul className={styles.log}>
                  {d.log.map((l) => (
                    <li key={l.id}>{ACCOUNTS.logRow(String(l.at).slice(0, 10).replaceAll('-', '.'), l.name, l.from, l.to, l.by)}</li>
                  ))}
                </ul>
              </Panel>
            </>
          )}
        </Loadable>
      </div>
      {creating && state.data ? (
        <CreateDialog
          roles={state.data.roles}
          onClose={() => setCreating(false)}
          onCreated={() => {
            setCreating(false);
            setDone(true);
            state.reload();
          }}
        />
      ) : null}
    </div>
  );
}

function CreateDialog({ roles, onClose, onCreated }) {
  const [role, setRole] = useState(roles[1]);
  const [gu, setGu] = useState('');
  const [team, setTeam] = useState('');
  const [name, setName] = useState('');
  const [loginId, setLoginId] = useState('');
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const district = role === '구 도로관리팀';

  const submit = async () => {
    setBusy(true);
    try {
      const r = await createAccount({ role, gu: district ? gu : null, team, name, loginId });
      if (r.ok) onCreated();
      else setErrors({ gu: r.code === 'guRequired', duplicate: r.code === 'duplicate' });
    } catch {
      reportActionError();
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      title={ACCOUNTS.dialogTitle}
      titleId="create-account-title"
      onClose={onClose}
      closeLabel={ACCOUNTS.dialogClose}
      footer={
        <Button variant="primary" loading={busy} disabled={!name.trim() || !loginId.trim()} onClick={submit}>
          {ACCOUNTS.create}
        </Button>
      }
    >
      <SelectInput label={ACCOUNTS.role} value={role} onChange={(v) => { setRole(v); setErrors({}); }} options={roles} />
      {district ? (
        <SelectInput label={ACCOUNTS.gu} value={gu} onChange={(v) => { setGu(v); setErrors({}); }} options={GU_LIST} placeholder="" error={errors.gu ? ACCOUNTS.errorGu : null} />
      ) : null}
      <TextInput label={ACCOUNTS.team} value={team} onChange={setTeam} placeholder={ACCOUNTS.teamPlaceholder} />
      <TextInput label={ACCOUNTS.name} value={name} onChange={setName} />
      <TextInput label={ACCOUNTS.loginId} value={loginId} onChange={(v) => { setLoginId(v); setErrors({}); }} error={errors.duplicate ? ACCOUNTS.errorDuplicate : null} />
    </Dialog>
  );
}
