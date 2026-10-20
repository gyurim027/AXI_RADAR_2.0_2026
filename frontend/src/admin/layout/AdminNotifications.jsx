import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listAdminNotifications, markAdminNotificationRead } from '../../api/admin.js';
import { useAuth } from '../../app/providers/AuthProvider.jsx';
import { useAsync } from '../../shared/hooks/useAsync.js';
import Icon from '../../user/components/Icon.jsx';
import { ADMIN_COPY } from '../copy.js';
import styles from './AdminNotifications.module.css';

/** 눌렀을 때 가는 화면 (AD-00 3-1): 실패 → 실행 기록 / 승인 결과 → 승인 이력 / 개정 → 규정 변경 / 갱신 예정일 지남 → 데이터 목록 */
const TARGET = {
  failure: '/admin/runs/log',
  approval: '/admin/standards/approvals',
  regulation: '/admin/standards/regulations',
  staleData: '/admin/data/list',
};

/** 알림: 종 아이콘에 안 읽은 수를 보이고, 누르면 최신 순 20개 목록이 열린다. */
export default function AdminNotifications() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const { data, reload, failed } = useAsync(() => listAdminNotifications(), [user.id]);
  const items = data || [];
  const unread = items.filter((n) => !n.read).length;
  const copy = ADMIN_COPY.notifications;

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

  const go = async (n) => {
    await markAdminNotificationRead({ id: n.id });
    setOpen(false);
    reload();
    navigate(TARGET[n.kind] || '/admin');
  };

  return (
    <div className={styles.wrap} ref={ref}>
      <button type="button" className={styles.bell} aria-haspopup="dialog" aria-expanded={open} aria-label={copy.label(unread)} onClick={() => { if (!open) reload(); setOpen((v) => !v); }}>
        <Icon name="bell" size={22} />
        {unread > 0 ? <span className={styles.count}>{unread}</span> : null}
      </button>
      {open ? (
        <div className={styles.panel} role="dialog" aria-label={copy.title}>
          <h2 className={styles.title}>{copy.title}</h2>
          {failed ? (
            <p className={styles.empty} role="alert">
              {copy.failed}
            </p>
          ) : items.length === 0 ? (
            <p className={styles.empty}>{copy.empty}</p>
          ) : (
            <ul className={styles.list}>
              {items.map((n) => (
                <li key={n.id}>
                  <button type="button" className={`${styles.item} ${n.read ? '' : styles.unread}`} onClick={() => go(n)}>
                    {`${n.text} · ${n.date}`}
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
