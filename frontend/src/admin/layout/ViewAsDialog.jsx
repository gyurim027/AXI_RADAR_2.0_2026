import { useState } from 'react';
import { COMMON } from '../../shared/copy/common.js';
import { useNavigate } from 'react-router-dom';
import { listViewAsOptions, startViewAs } from '../../api/admin.js';
import { useAuth } from '../../app/providers/AuthProvider.jsx';
import { useAsync } from '../../shared/hooks/useAsync.js';
import Button from '../components/Button.jsx';
import Dialog from '../components/Dialog.jsx';
import { SelectInput } from '../components/Field.jsx';
import { ErrorState } from '../components/States.jsx';
import { ADMIN_COPY } from '../copy.js';

/** AD-00 4-1 사용자 화면 보기: 볼 계정을 고르고 보기 전용으로 연다. 열람은 접속 기록에 남는다. */
export default function ViewAsDialog({ onClose }) {
  const copy = ADMIN_COPY.viewAs;
  const { refreshUser } = useAuth();
  const navigate = useNavigate();
  const { data, failed, reload } = useAsync(() => listViewAsOptions(), []);
  const [account, setAccount] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const value = account || data?.[0]?.value || '';

  const open = async () => {
    setBusy(true);
    setError(false);
    try {
      await startViewAs({ accountId: value });
      refreshUser();
      navigate('/candidates', { replace: true });
    } catch {
      setError(true);
      setBusy(false);
    }
  };

  return (
    <Dialog
      title={copy.title}
      titleId="view-as-title"
      subtitle={copy.subtitle}
      onClose={onClose}
      closeLabel={copy.closeLabel}
      footer={
        <Button variant="primary" loading={busy} onClick={open} disabled={!value}>
          {copy.open}
        </Button>
      }
    >
      {failed ? <ErrorState areaName="볼 계정 목록" onRetry={reload} /> : <SelectInput label={copy.account} value={value} onChange={setAccount} options={data || []} />}
      {error ? (
        <p role="alert" style={{ color: 'var(--radar-admin-semantic-color-danger)' }}>
          {COMMON.loadFailed('사용자 화면')}
        </p>
      ) : null}
    </Dialog>
  );
}
