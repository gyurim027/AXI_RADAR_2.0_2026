import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../../../components/Button.jsx';
import Icon from '../../../components/Icon.jsx';
import Modal from '../../../components/Modal.jsx';
import { ErrorState, SkeletonBlock } from '../../../components/States.jsx';
import { confirmGu, getConfirmSummary } from '../../../../api/candidates.js';
import { useAsync } from '../../../../shared/hooks/useAsync.js';
import { ROLE } from '../../../../shared/constants.js';
import { COMMON } from '../../../../shared/copy/common.js';
import { CONFIRM } from '../copy.js';
import styles from './ConfirmModal.module.css';

/**
 * US-04 구 확정
 * - 시 도로과: 3개 구 확정 현황만 본다. 확정할 수 없다.
 * - 도로관리팀: 확정 확인 → 확정 완료. 다른 구의 진행 상황과 회차 확정 조건은 구 화면에 쓰지 않는다 (ISS-029).
 * 바깥을 눌러도 닫히지 않는다. 확정은 되돌릴 수 없는 일이기 때문이다 (디자인 시스템 8장).
 */
export default function ConfirmModal({ runId, role, onClose, onConfirmed, onFailed }) {
  const { data, failed, reload, loading } = useAsync(() => getConfirmSummary({ runId }), [runId]);
  const [stage, setStage] = useState('ask'); // ask | done
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const navigate = useNavigate();

  const doConfirm = async () => {
    setBusy(true);
    setErr('');
    try {
      await confirmGu({ runId });
      setStage('done');
      onConfirmed();
    } catch {
      setErr(COMMON.saveFailed);
      onFailed?.(); // POL-024
    } finally {
      setBusy(false);
    }
  };

  if (role === ROLE.CITY) {
    return (
      <Modal title={CONFIRM.cityTitle} titleId="confirm-title" onClose={onClose} closeLabel={CONFIRM.close}>
        {failed ? (
          <ErrorState areaName="확정 현황" onRetry={reload} />
        ) : loading && !data ? (
          <SkeletonBlock />
        ) : (
          <div className={styles.body}>
            <p>{data.guStatuses.map((s) => CONFIRM.cityStatus(s.gu, s.done, s.date)).join(' · ')}</p>
            <div className={styles.actions}>
              <Button variant="soft" onClick={onClose}>
                {CONFIRM.close}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    );
  }

  // 도로관리팀
  const gu = data?.gu;
  if (stage === 'done') {
    return (
      <Modal title={CONFIRM.doneTitle(gu)} titleId="confirm-title" onClose={onClose}>
        <div className={styles.body}>
          <p>{CONFIRM.doneNote}</p>
          <div className={styles.actions}>
            <Button
              onClick={() => {
                onClose();
                navigate('/reports/annual');
              }}
            >
              {CONFIRM.doneButton}
            </Button>
          </div>
        </div>
      </Modal>
    );
  }
  return (
    <Modal title={gu ? CONFIRM.title(gu) : '점검 대상을 확정할까요?'} titleId="confirm-title" onClose={onClose}>
      {failed ? (
        <ErrorState areaName="확정 현황" onRetry={reload} />
      ) : loading && !data ? (
        <SkeletonBlock />
      ) : (
        <div className={styles.body}>
          <p className={styles.sub}>{CONFIRM.sub(gu)}</p>
          <p className={`${styles.numbers} num`}>{CONFIRM.numbers(data.counts)}</p>
          {data.counts.none > 0 ? (
            <p className={styles.warn} role="alert">
              <Icon name="warning" size={18} />
              <span>{CONFIRM.warning(data.counts.none)}</span>
            </p>
          ) : null}
          {err ? (
            <p className={styles.warn} role="alert">
              {err}
            </p>
          ) : null}
          <div className={styles.actions}>
            <Button variant="soft" onClick={onClose}>
              {CONFIRM.more}
            </Button>
            <Button onClick={doConfirm} loading={busy}>
              {CONFIRM.confirm}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
