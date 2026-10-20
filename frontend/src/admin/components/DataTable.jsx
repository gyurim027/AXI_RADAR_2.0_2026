import { Fragment } from 'react';
import Icon from '../../user/components/Icon.jsx';
import styles from './DataTable.module.css';

/**
 * 어드민 표 (디자인 시스템 9-3, 10장)
 * columns: { key, header, align('left'|'right'), width, render(row), first(첫 열: 500 굵기), nowrap }
 * expandedKey / renderExpanded: 행을 누르면 그 행 아래에 칸이 열린다.
 * maxHeight: 긴 표는 안에서 스크롤하고 머리 줄을 고정한다.
 * compact: 조밀(행 40px, 글자 14px)
 */
export default function DataTable({
  caption,
  columns,
  rows,
  getRowKey,
  onRowClick,
  expandedKey,
  renderExpanded,
  rowLabel,
  maxHeight,
  compact = false,
  emptyContent,
  footer,
  selectedKey,
}) {
  const expandable = typeof renderExpanded === 'function';
  const clickable = !!onRowClick;
  return (
    <div className={styles.wrap}>
      <div className={styles.scroll} style={maxHeight ? { maxHeight } : undefined} tabIndex={0} role="region" aria-label={caption}>
        <table className={`${styles.table} ${compact ? styles.compact : ''}`}>
          {caption ? <caption className="sr-only">{caption}</caption> : null}
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key} scope="col" className={`${styles.th} ${c.align === 'right' ? styles.right : ''}`} style={c.width ? { width: c.width, minWidth: c.width } : undefined}>
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const key = getRowKey(row);
              const open = expandable && expandedKey === key;
              const selected = selectedKey != null && selectedKey === key;
              return (
                <Fragment key={key}>
                  <tr
                    className={`${styles.tr} ${clickable || expandable ? styles.clickable : ''} ${open ? styles.open : ''} ${selected ? styles.selected : ''}`}
                    tabIndex={clickable || expandable ? 0 : undefined}
                    aria-expanded={expandable ? open : undefined}
                    aria-label={clickable || expandable ? rowLabel?.(row) : undefined}
                    onClick={clickable || expandable ? () => onRowClick?.(row) : undefined}
                    onKeyDown={
                      clickable || expandable
                        ? (e) => {
                            if (e.target !== e.currentTarget) return;
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              onRowClick?.(row);
                            }
                          }
                        : undefined
                    }
                  >
                    {columns.map((c, i) => (
                      <td key={c.key} className={`${styles.td} ${c.align === 'right' ? styles.right : ''} ${c.first ? styles.first : ''} ${c.nowrap ? styles.nowrap : ''}`}>
                        {expandable && i === 0 ? (
                          <span className={styles.chev} aria-hidden="true">
                            <Icon name={open ? 'chevronUp' : 'chevronDown'} size={16} />
                          </span>
                        ) : null}
                        {c.render ? c.render(row) : row[c.key]}
                      </td>
                    ))}
                  </tr>
                  {open ? (
                    <tr className={styles.expandedRow}>
                      <td colSpan={columns.length} className={styles.expandedCell}>
                        {renderExpanded(row)}
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
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
      </div>
      {footer ? <div className={styles.footer}>{footer}</div> : null}
    </div>
  );
}
