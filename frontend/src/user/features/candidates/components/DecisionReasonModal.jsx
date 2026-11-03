import { useState } from 'react';
import Button from '../../../components/Button.jsx';
import Modal from '../../../components/Modal.jsx';
import { SelectField, TextField } from '../../../components/FormControls.jsx';
import { saveDecision } from '../../../../api/candidates.js';
import { COMMON } from '../../../../shared/copy/common.js';
import { DRAWER } from '../copy.js';
import styles from './tabs/Tabs.module.css';

const OTHER = '기타';

/**
 * 사유 입력 창 (US-03 5-2). 표의 결정 상태 칸과 서랍 ⑤ 탭이 같이 쓴다.
 * 제외·보류는 사유가 있어야 저장된다. 사유 규칙과 저장은 기존 기능 그대로다.
 */
export default function DecisionReasonModal({ runId, gid, decision, onClose, onSaved, onFailed }) {
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
    } catch (e) {
      // 개발용 결정 저장은 최초 결정만 받는다. 이미 결정한 후보를 다시 저장하면 서버가 409로 거절한다.
      setError(e?.status === 409 ? DRAWER.alreadyDecided : COMMON.saveFailed);
      onFailed?.(); // 처리됐는지 모를 수 있어 목록과 상태를 다시 불러와 먼저 확인하게 한다 (POL-024)
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
