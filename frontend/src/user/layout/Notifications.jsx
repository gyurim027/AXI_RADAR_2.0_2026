import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listNotifications, markNotificationRead } from '../../api/session.js';
import { useAsync } from '../../shared/hooks/useAsync.js';
import { useAuth } from '../../app/providers/AuthProvider.jsx';
import { useRun } from '../../app/providers/RunProvider.jsx';
import Icon from '../components/Icon.jsx';
import styles from './Notifications.module.css';

/** 알림 (US-00 4-1). 종 아이콘에 안 읽은 수를 보이고, 누르면 최신 순 20개 목록이 열린다. */
export default function Notifications() {
  const { user } = useAuth();
  const { setRunId } = useRun();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const { data, reload, failed } = useAsync(() => listNotifications(), [user.id]);
  const items = data || [];
  const unread = items.filter((n) => !n.read).length;

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  // 알림을 누르면 그 일을 하는 화면으로 간다
  const go = async (n) => {
    await markNotificationRead({ id: n.id });
    setOpen(false);
    reload();
    if (n.kind === 'approval') navigate('/reference/approvals');
    else if (n.kind === 'regulation') navigate('/reference/regulations');
    else {
      if (n.targetRunId) setRunId(n.targetRunId);
      navigate('/candidates');
    }
  };

  return (
    <div className={styles.wrap} ref={ref}>
      <button type="button" className={styles.bell} aria-haspopup="true" aria-expanded={open} aria-label={`알림 ${unread}개 보기`} title="알림" onClick={() => setOpen((v) => !v)}>
        <Icon name="bell" size={22} />
        {unread > 0 ? <span className={styles.count}>{unread}</span> : null}
      </button>
      {open ? (
        <div className={styles.panel} role="dialog" aria-label="알림">
          <h2 className={styles.title}>알림</h2>
          {failed ? (
            <p className={styles.empty} role="alert">
              알림을 불러오지 못했습니다.
            </p>
          ) : items.length === 0 ? (
            <p className={styles.empty}>새 알림이 없습니다.</p>
          ) : (
            <ul className={styles.list}>
              {items.map((n) => (
                <li key={n.id}>
                  <button type="button" className={`${styles.item} ${n.read ? '' : styles.unread}`} onClick={() => go(n)}>
                    <span>{`${n.text} · ${n.date}`}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
