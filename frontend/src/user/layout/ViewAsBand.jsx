import { useNavigate } from 'react-router-dom';
import { getViewAsLabel, stopViewAs } from '../../api/admin.js';
import { useAuth } from '../../app/providers/AuthProvider.jsx';
import { ADMIN_COPY } from '../../admin/copy.js';
import { fillVars } from '../../shared/utils/format.js';
import styles from './StatusBand.module.css';

/** 운영자가 사용자 화면 보기로 들어왔을 때 늘 보이는 띠 (AD-00 4-1). 닫을 수 없다. */
export default function ViewAsBand() {
  const { refreshUser } = useAuth();
  const navigate = useNavigate();
  const back = async () => {
    await stopViewAs();
    refreshUser();
    navigate('/admin', { replace: true });
  };
  return (
    <div className={`${styles.band} ${styles.ref}`} role="status">
      <span>{fillVars(ADMIN_COPY.viewAs.band, { '볼 계정': getViewAsLabel() || '' })}</span>
      <button type="button" className={styles.linkBtn} onClick={back}>
        {ADMIN_COPY.viewAs.back}
      </button>
    </div>
  );
}
