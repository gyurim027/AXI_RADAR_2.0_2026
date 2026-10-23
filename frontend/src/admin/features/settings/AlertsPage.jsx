import { useState } from 'react';
import { getAlertEmail, saveAlertEmail } from '../../../api/admin.js';
import { useAsync } from '../../../shared/hooks/useAsync.js';
import Button from '../../components/Button.jsx';
import { TextInput } from '../../components/Field.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Panel, { Banner } from '../../components/Panel.jsx';
import { ALERTS } from './copy.js';
import styles from './Settings.module.css';
import { reportActionError } from '../../utils/actionError.js';

/** AD-17 알림 설정 (유형 C): 수집·산정 실패 알림을 받을 메일을 정한다. 여러 개는 쉼표로 나눠 적는다. */
export default function AlertsPage() {
  const state = useAsync(() => getAlertEmail(), []);
  return (
    <div>
      <PageHeader title={ALERTS.title} subtitle={ALERTS.subtitle} />
      <Loadable state={state} areaName={ALERTS.failedArea} rows={3}>{(d) => <AlertsForm initial={d.value} />}</Loadable>
    </div>
  );
}

function AlertsForm({ initial }) {
  const [value, setValue] = useState(initial);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setDone(false);
    try {
      const r = await saveAlertEmail({ value });
      if (r.ok) {
        setError('');
        setDone(true);
      } else setError(ALERTS.error);
    } catch {
      reportActionError();
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel className={styles.formPanel}>
      <form className={styles.form} onSubmit={submit} noValidate>
        <TextInput label={ALERTS.label} value={value} onChange={(v) => { setValue(v); setError(''); setDone(false); }} help={ALERTS.help} error={error} />
        {done ? <Banner tone="success">{ALERTS.done}</Banner> : null}
        <div className={styles.actions}>
          <Button type="submit" variant="primary" loading={busy}>
            {ALERTS.save}
          </Button>
        </div>
      </form>
    </Panel>
  );
}
