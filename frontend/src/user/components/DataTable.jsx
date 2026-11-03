import Icon from './Icon.jsx';
import styles from './DataTable.module.css';

/**
 * 표 (디자인 시스템 11-3, 14장)
 * 정렬은 한 규칙이다: 머리 줄과 첫 열은 가운데, 나머지 칸은 왼쪽 (열마다 정하지 않는다).
 * columns: { key, header, width, sticky, sortable, render(row) }
 *   - sticky 열은 앞쪽에 이어서 놓는다. width(px)가 필요하다.
 * 열이 넘치면 가로로 스크롤하고, 열을 숨기지 않는다.
 * stickyRight: 맨 오른쪽 열을 고정해, 표가 가로로 스크롤돼도 늘 보이게 한다(결정 상태 칸).
 * fixed: 열 폭을 그대로 쓴다. 남는 폭은 fill 열 하나가 받는다(순위 열 같은 좁은 열이 넓어지지 않게 한다).
 */
export default function DataTable({
  caption,
  columns,
  rows,
  getRowKey,
  selectedKey,
  onRowClick,
  sort,
  onSort,
  rowTone,
  minWidth,
  emptyContent,
  rowLabel,
  fixed = false,
}) {
  const lefts = columns.map((c, i) =>
    c.sticky ? columns.slice(0, i).reduce((sum, prev) => sum + (prev.sticky ? prev.width || 0 : 0), 0) : null,
  );
  const lastSticky = columns.reduce((acc, c, i) => (c.sticky ? i : acc), -1);

  const fixedTotal = columns.reduce((sum, c) => sum + (c.width || 0), 0);
  return (
    <table className={`${styles.table} ${fixed ? styles.fixed : ''}`} style={{ minWidth: fixed ? fixedTotal : minWidth }}>
      {caption ? <caption className="sr-only">{caption}</caption> : null}
      {fixed ? (
        <colgroup>
          {columns.map((c) => (
            <col key={c.key} style={c.fill ? undefined : { width: c.width }} />
          ))}
        </colgroup>
      ) : null}
      <thead>
        <tr>
          {columns.map((c, i) => {
            const active = sort && sort.key === c.key;
            const style = {
              ...(fixed ? null : { width: c.width, minWidth: c.width }), // 고정 모드는 colgroup이 폭을 정한다
              left: lefts[i] ?? undefined,
              textAlign: 'center',
            };
            return (
              <th
                key={c.key}
                scope="col"
                className={`${styles.th} ${c.headerWrap ? styles.wrapHead : ''} ${c.sticky ? styles.sticky : ''} ${c.stickyRight ? styles.stickyRight : ''} ${i === lastSticky ? styles.edge : ''}`}
                style={style}
                aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : c.sortable ? 'none' : undefined}
              >
                {c.sortable ? (
                  <button type="button" className={styles.sortBtn} onClick={() => onSort?.(c.key)}>
                    <span>{c.header}</span>
                    <Icon name={active && sort.dir === 'asc' ? 'sortUp' : 'sortDown'} size={14} className={active ? styles.sortOn : styles.sortOff} />
                  </button>
                ) : (
                  c.header
                )}
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const key = getRowKey(row);
          const selected = selectedKey != null && key === selectedKey;
          const tone = rowTone?.(row);
          return (
            <tr
              key={key}
              className={`${styles.tr} ${selected ? styles.selected : ''} ${tone === 'high' ? styles.high : ''} ${onRowClick ? styles.clickable : ''}`}
              tabIndex={onRowClick ? 0 : undefined}
              aria-current={selected ? 'true' : undefined}
              aria-label={onRowClick ? rowLabel?.(row) : undefined}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              onKeyDown={
                onRowClick
                  ? (e) => {
                      if (e.target !== e.currentTarget) return;
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        onRowClick(row);
                      }
                    }
                  : undefined
              }
              data-row-key={key}
            >
              {columns.map((c, i) => (
                <td
                  key={c.key}
                  className={`${styles.td} ${c.sticky ? styles.sticky : ''} ${c.stickyRight ? styles.stickyRight : ''} ${i === lastSticky ? styles.edge : ''}`}
                  style={{ textAlign: i === 0 ? 'center' : 'left', left: lefts[i] ?? undefined, ...(fixed ? null : { width: c.width, minWidth: c.width }) }}
                >
                  {c.render ? c.render(row) : row[c.key]}
                </td>
              ))}
            </tr>
          );
        })}
        {rows.length === 0 && emptyContent ? (
          <tr>
            <td colSpan={columns.length} className={styles.emptyCell}>
              {emptyContent}
            </td>
          </tr>
        ) : null}
      </tbody>
    </table>
  );
}
