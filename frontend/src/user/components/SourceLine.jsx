import { COMMON } from '../../shared/copy/common.js';
import styles from './SourceLine.module.css';

/** 지도·파일 출처 줄 (CM-00 14번). withComplaint: 민원 출처 줄(2번째 줄)도 보인다. */
export default function SourceLine({ withComplaint = false, className = '' }) {
  return (
    <div className={`${styles.source} ${className}`}>
      <p>{COMMON.sourceMap}</p>
      {withComplaint ? <p>{COMMON.sourceComplaint}</p> : null}
    </div>
  );
}
