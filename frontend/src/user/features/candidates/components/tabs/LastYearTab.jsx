import { DECISION } from '../../../../../shared/constants.js';
import { DRAWER } from '../../copy.js';
import styles from './Tabs.module.css';

/** ④ 작년 결정 (US-03 4-1). 작년에 제외·보류였으면 안내 문구를 주황 띠로 보인다. */
export default function LastYearTab({ detail }) {
  const ly = detail.lastYear;
  const warn = ly && (ly.decision === DECISION.EXCLUDE || ly.decision === DECISION.HOLD);
  return (
    <section>
      <p className={styles.sub}>{DRAWER.lastSub}</p>
      <div className={styles.content}>
        {ly ? (
          <>
            <p className={`${styles.notice} ${warn ? styles.noticeWarn : ''}`}>{DRAWER.lastNotice(ly.runName, ly.decision)}</p>
            <p>{DRAWER.lastReason(ly.reason, ly.memo)}</p>
          </>
        ) : (
          <p className={styles.muted}>{DRAWER.lastEmpty}</p>
        )}
      </div>
    </section>
  );
}
