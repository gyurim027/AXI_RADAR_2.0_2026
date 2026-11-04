import Icon from './Icon.jsx';
import styles from './Pagination.module.css';

function pageList(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const set = new Set([1, total, current, current - 1, current + 1]);
  const pages = [...set].filter((p) => p >= 1 && p <= total).sort((a, b) => a - b);
  const out = [];
  pages.forEach((p, i) => {
    if (i && p - pages[i - 1] > 1) out.push('…');
    out.push(p);
  });
  return out;
}

/** 쪽 번호 줄. 지금 쪽은 굵은 검정, 나머지는 옅은 회색 (디자인 시스템 11-3) */
export default function Pagination({ page, total, onChange }) {
  if (total <= 1) return null;
  const pages = pageList(page, total);
  return (
    <nav className={styles.nav} aria-label="쪽 이동">
      <button type="button" className={styles.arrow} onClick={() => onChange(page - 1)} disabled={page <= 1} aria-label="이전 쪽">
        <Icon name="chevronLeft" size={18} />
      </button>
      {pages.map((p, i) =>
        p === '…' ? (
          <span key={`gap-${i}`} className={styles.gap} aria-hidden="true">
            …
          </span>
        ) : (
          <button
            key={p}
            type="button"
            className={`${styles.page} ${p === page ? styles.current : ''} num`}
            aria-current={p === page ? 'page' : undefined}
            aria-label={`${p}쪽`}
            onClick={() => onChange(p)}
          >
            {p}
          </button>
        ),
      )}
      <button type="button" className={styles.arrow} onClick={() => onChange(page + 1)} disabled={page >= total} aria-label="다음 쪽">
        <Icon name="chevronRight" size={18} />
      </button>
    </nav>
  );
}
