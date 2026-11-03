import { Link } from 'react-router-dom';
import { RUN_STATUS } from '../../shared/constants.js';
import { runTitle, runYear } from '../../shared/utils/format.js';
import styles from './StatusBand.module.css';

/** 점검 해 상태 띠 (US-00 3-1). 검토 중이 아닌 회차를 볼 때 늘 보인다. 닫을 수 없다. */
export default function StatusBand({ run }) {
  const isRef = run.status === RUN_STATUS.REF;
  return (
    <div className={`${styles.band} ${isRef ? styles.ref : styles.final}`} role="status">
      {isRef ? (
        <>
          <span>{`${runTitle(run, false)}은 참고용입니다. 바뀐 자료로 다시 계산한 순위라 결정에는 쓰지 않습니다.`}</span>
          <Link to="/reports/half-year" className={styles.link}>
            요약 보기
          </Link>
        </>
      ) : (
        <span>{`${runYear(run.name)}년 점검 대상이 확정되었습니다. 열람만 가능합니다.`}</span>
      )}
    </div>
  );
}
