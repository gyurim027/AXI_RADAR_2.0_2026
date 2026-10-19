import { COMMON } from '../../shared/copy/common.js';
import Button from './Button.jsx';
import styles from './States.module.css';

/** 빈 목록 (CM-00 11번). 필터 때문일 때만 버튼을 더한다. */
export function EmptyState({ text, hint, actionLabel, onAction, children }) {
  return (
    <div className={styles.state}>
      <p className={styles.main}>{text}</p>
      {hint ? <p className={styles.hint}>{hint}</p> : null}
      {actionLabel ? (
        <Button variant="soft" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
      {children}
    </div>
  );
}

/** 불러오기 실패 (CM-00 12번). 실패한 영역 안에만 띄우고 높이는 그대로 둔다. */
export function ErrorState({ areaName, onRetry }) {
  return (
    <div className={styles.state} role="alert">
      <p className={styles.main}>{COMMON.loadFailed(areaName)}</p>
      <p className={styles.hint}>{COMMON.loadFailedHint}</p>
      <Button variant="soft" onClick={onRetry}>
        {COMMON.loadFailedRetry}
      </Button>
    </div>
  );
}

/** 불러오는 중 회색 뼈대 (CM-00 13번). 1초 안이면 쓰지 않는다. */
export function SkeletonRows({ rows = 8 }) {
  return (
    <div className={styles.skeleton} aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className={styles.skelRow} />
      ))}
    </div>
  );
}
export function SkeletonBlock({ className = '' }) {
  return <div className={`${styles.skelBlock} ${className}`} aria-hidden="true" />;
}
