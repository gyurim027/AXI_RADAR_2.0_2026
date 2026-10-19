import DataTable from '../../../components/DataTable.jsx';
import Button from '../../../components/Button.jsx';
import { LIST } from '../copy.js';
import styles from './GuCompare.module.css';

/** US-01 3-1 구별 비교. 시 도로과만 본다 (ISS-029). 표 자리가 구별 비교로 바뀌고 마지막 버튼으로 돌아온다. */
export default function GuCompare({ rows, onBack }) {
  const H = LIST.compareHead;
  const pct = (v) => <span className="num">{`${v}%`}</span>;
  const columns = [
    { key: 'gu', header: H[0], render: (r) => r.gu },
    { key: 'top', header: H[1], align: 'right', render: (r) => pct(r.topRatio) },
    { key: 'acc', header: H[2], align: 'right', render: (r) => pct(r.accidentRatio) },
    { key: 'before', header: H[3], align: 'right', render: (r) => pct(r.beforeRatio) },
  ];
  return (
    <div className={styles.box}>
      <h2 className={styles.title}>{LIST.compareTitle}</h2>
      <p className={styles.body}>{LIST.compareBody}</p>
      <DataTable caption={LIST.compareTitle} columns={columns} rows={rows} getRowKey={(r) => r.gu} />
      <div className={styles.back}>
        <Button variant="soft" onClick={onBack}>
          {LIST.compareBack}
        </Button>
      </div>
    </div>
  );
}
