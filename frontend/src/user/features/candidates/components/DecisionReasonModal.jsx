import { useState } from 'react';
import Button from '../../../components/Button.jsx';
import Modal from '../../../components/Modal.jsx';
import { SelectField, TextField } from '../../../components/FormControls.jsx';
import { saveDecision } from '../../../../api/candidates.js';
import { DRAWER } from '../copy.js';
import styles from './tabs/Tabs.module.css';

const OTHER = '기타';

/**
 * 사유 입력 창 (US-03 5-2). 표의 결정 상태 칸과 서랍 ⑤ 탭이 같이 쓴다.
 * 제외·보류는 사유가 있어야 저장된다. 사유 규칙과 저장은 기존 기능 그대로다.
 */
export default function DecisionReasonModal({ runId, gid, decision, onClose, onSaved }) {
  const [reasonKey, setReasonKey] = useState('');
  const [other, setOther] = useState('');
  const [memo, setMemo] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const isOther = reasonKey === OTHER;

  const save = async () => {
    setBusy(true);
    setError('');
    try {
      const r = await saveDecision({
        runId,
        gid,
        decision,
        reasonKey: reasonKey || null,
        reasonText: isOther ? other : null,
        memo: isOther ? null : memo,
      });
      if (r.ok) onSaved();
      else setError(r.code === 'otherRequired' ? DRAWER.otherRequired : DRAWER.reasonRequired);
    } catch {
      setError('결정을 저장하지 못했습니다. 잠시 뒤 다시 시도해 주세요.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title={DRAWER.reasonModalTitle(decision)} titleId="reason-title" onClose={onClose} closeLabel={DRAWER.modalClose}>
      <div className={styles.content}>
        <SelectField
          inline={false}
          label={DRAWER.reasonLabel}
          id="reason-select"
          value={reasonKey}
          onChange={(v) => {
            setReasonKey(v);
            setError('');
          }}
          placeholder={DRAWER.reasonPlaceholder}
          options={DRAWER.reasonOptionsByDecision[decision] || []}
        />
        {isOther ? (
          <TextField label={DRAWER.otherLabel} value={other} onChange={setOther} maxLength={100} placeholder={DRAWER.otherPlaceholder} />
        ) : (
          <TextField label={DRAWER.memoLabel} value={memo} onChange={setMemo} maxLength={200} />
        )}
        {error ? (
          <p className={styles.err} role="alert">
            {error}
          </p>
        ) : null}
        <div className={styles.right} style={{ justifyContent: 'flex-end' }}>
          <Button onClick={save} loading={busy}>
            {DRAWER.saveDecision}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
