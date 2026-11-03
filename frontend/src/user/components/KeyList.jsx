import styles from './KeyList.module.css';

/** 줄 목록: 항목마다 작은 점과 14px 글자, 항목 사이 8px. */
export default function KeyList({ items }) {
  return (
    <ul className={styles.list}>
      {items.map((t, i) => (
        <li key={`${i}-${t}`} className={styles.item}>
          {t}
        </li>
      ))}
    </ul>
  );
}
