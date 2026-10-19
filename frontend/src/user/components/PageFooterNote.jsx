import { COMMON } from '../../shared/copy/common.js';
import styles from './PageFooterNote.module.css';

/** 순위 안내 (CM-00 7번). 순위가 나오는 화면의 가장 아래에 한 줄로 늘 둔다. 닫을 수 없다. */
export default function PageFooterNote({ className = '' }) {
  return (
    <p className={`${styles.note} ${className}`} role="note">
      {COMMON.rankNotice}
    </p>
  );
}
