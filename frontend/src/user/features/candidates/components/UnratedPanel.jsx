import { useId } from 'react';
import DataTable from '../../../components/DataTable.jsx';
import Icon from '../../../components/Icon.jsx';
import styles from './UnratedPanel.module.css';
import { LIST } from '../copy.js';

/**
 * 3 평가하지 못한 구역. 데이터 결측으로 평가 대상에서 제외된 곳이다(KPI 전체에 들어가지 않는다).
 * 펼치면 구역마다 수집한 데이터와 내용, 수집하지 못한 데이터와 이유를 보인다.
 */
export default function UnratedPanel({ rows, city, open, onToggle, selectedId, onSelect }) {
  const id = useId();
  const H = LIST.unratedHead;
  const columns = [
    ...(city ? [{ key: 'gu', header: LIST.unratedHeadCity, width: 80, render: (r) => r.gu }] : []),
    {
      key: 'name',
      header: H[0],
      width: 210,
      render: (r) => (
        <span className={styles.name}>
          <span className={styles.addr}>{r.address}</span>
          <span className={styles.landmark}>{r.landmark}</span>
        </span>
      ),
    },
    {
      key: 'collected',
      header: H[1],
      width: 250,
      render: (r) =>
        r.collected.length ? (
          <ul className={styles.items}>
            {r.collected.map((c) => (
              <li key={c.name}>
                <strong>{c.name}</strong>
                <span>{c.value}</span>
              </li>
            ))}
          </ul>
        ) : (
          '-'
        ),
    },
    {
      key: 'missing',
      header: H[2],
      fill: true,
      width: 300,
      render: (r) =>
        r.missing.length ? (
          <ul className={styles.items}>
            {r.missing.map((m) => (
              <li key={m.name}>
                <strong>{m.name}</strong>
                <span>{m.reason}</span>
              </li>
            ))}
          </ul>
        ) : (
          '-'
        ),
    },
  ];

  return (
    <section className={styles.card}>
      <h2 className={styles.head}>
        <button type="button" className={styles.btn} aria-expanded={open} aria-controls={id} onClick={onToggle}>
          <span className={styles.title}>{LIST.unratedTitle(rows.length)}</span>
          <span className={styles.desc}>{LIST.unratedDesc}</span>
          <Icon name={open ? 'chevronUp' : 'chevronDown'} size={22} className={styles.chev} />
        </button>
      </h2>
      {open ? (
        <div id={id} className={styles.body}>
          <DataTable caption={LIST.unratedTitle(rows.length)} columns={columns} rows={rows} getRowKey={(r) => r.gid} selectedKey={selectedId} onRowClick={(r) => onSelect(r.gid)} rowLabel={(r) => `${r.address} ${r.landmark}`} fixed />
        </div>
      ) : null}
    </section>
  );
}
