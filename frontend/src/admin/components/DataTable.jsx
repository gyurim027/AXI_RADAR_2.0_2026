import { Fragment, useRef } from 'react';
import useFirstColumnCenter from '../../shared/hooks/useFirstColumnCenter.js';
import Icon from '../../user/components/Icon.jsx';
import { useDensity } from '../utils/density.js';
import styles from './DataTable.module.css';

/**
 * 어드민 표 (디자인 시스템 9-3, 10장)
 * 정렬은 한 규칙이다: 머리 줄은 가운데, 나머지 칸은 왼쪽. 첫 열은 본문 칸이 모두 3자 이하(숫자만이면 길이 무관)일 때만 가운데다. align: 'right'는 숫자 폭만 맞춘다.
 * columns: { key, header, align('right'면 숫자 폭 맞춤), width, render(row), first(첫 열: 500 굵기), nowrap }
 * expandedKey / renderExpanded: 행을 누르면 그 행 아래에 칸이 열린다.
 * maxHeight: 긴 표는 안에서 스크롤하고 머리 줄을 고정한다.
 * compact: 조밀(행 40px, 글자 14px). 정하지 않으면 화면 위의 '표 밀도' 선택을 따른다(촘촘히가 기본).
 */
export default function DataTable({
  caption,
  columns,
  rows,
  getRowKey,
  onRowClick,
  expandedKey,
  renderExpanded,
  canExpand,
  rowLabel,
  maxHeight,
  compact,
  emptyContent,
  footer,
  selectedKey,
}) {
  const density = useDensity();
  const tbodyRef = useRef(null);
  const firstCenter = useFirstColumnCenter(tbodyRef, rows);
  const dense = compact ?? density === 'compact';
  const expandable = typeof renderExpanded === 'function';
  const clickable = !!onRowClick;
  // 열 폭이 모두 정해져 있으면 그 합보다 좁아지지 않게 하고, 모자라면 가로로 스크롤한다 (열을 숨기지 않는다)
  const total = columns.every((c) => c.width) ? columns.reduce((sum, c) => sum + c.width, 0) : undefined;
  return (
    <div className={styles.wrap}>
      <div className={styles.scroll} style={maxHeight ? { maxHeight } : undefined} tabIndex={0} role="region" aria-label={caption}>
        <table className={`${styles.table} ${dense ? styles.compact : ''} ${firstCenter ? styles.firstCenter : ''}`} style={total ? { minWidth: total } : undefined}>
          {caption ? <caption className="sr-only">{caption}</caption> : null}
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key} scope="col" className={styles.th} style={c.width ? { width: c.width, minWidth: c.width } : undefined}>
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody ref={tbodyRef}>
            {rows.map((row) => {
              const key = getRowKey(row);
              const open = expandable && expandedKey === key;
              const selected = selectedKey != null && selectedKey === key;
              return (
                <Fragment key={key}>
                  <tr
                    className={`${styles.tr} ${clickable || expandable ? styles.clickable : ''} ${open ? styles.open : ''} ${selected ? styles.selected : ''}`}
                    tabIndex={clickable && !expandable ? 0 : undefined}
                    aria-label={clickable && !expandable ? rowLabel?.(row) : undefined}
                    onClick={clickable || expandable ? () => onRowClick?.(row) : undefined}
                    onKeyDown={
                      clickable && !expandable
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
                        {expandable && i === 0 && canExpand?.(row) !== false ? (
                          <button
                            type="button"
                            className={styles.chev}
                            aria-expanded={open}
                            aria-label={rowLabel?.(row)}
                            onClick={(e) => {
                              e.stopPropagation();
                              onRowClick?.(row);
                            }}
                          >
                            <Icon name={open ? 'chevronUp' : 'chevronDown'} size={16} />
                          </button>
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
