import { Link } from 'react-router-dom';
import { RUN_STATUS } from '../../shared/constants.js';
import { runNameWithoutRef } from '../../shared/utils/format.js';
import styles from './StatusBand.module.css';

/** 회차 상태 띠 (US-00 3-1). 검토 중이 아닌 회차를 볼 때 늘 보인다. 닫을 수 없다. */
export default function StatusBand({ run }) {
  const isRef = run.status === RUN_STATUS.REF;
  return (
    <div className={`${styles.band} ${isRef ? styles.ref : styles.final}`} role="status">
      {isRef ? (
        <>
          <span>{`${runNameWithoutRef(run.name)} 참고 회차입니다. 바뀐 자료로 다시 계산한 순위라 결정에는 쓰지 않습니다.`}</span>
          <Link to="/reports/half-year" className={styles.link}>
            요약 보기
          </Link>
        </>
      ) : (
        <span>{`${run.name} 점검 대상이 확정된 회차입니다. 보기만 할 수 있습니다.`}</span>
      )}
    </div>
  );
}
