import { EmptyState } from '../../../components/States.jsx';
import { ANNUAL } from '../copy.js';
import { ReportCard } from './ReportParts.jsx';
import styles from './PreviewGroups.module.css';

/** 점검 요청서 미리보기: 담당 부서 묶음마다 우선 점검 대상을 한 줄씩 보인다(US-05, H-01). */
export default function PreviewGroups({ groups }) {
  if (!groups.length) {
    return (
      <ReportCard>
        <EmptyState text={ANNUAL.groupEmpty} />
      </ReportCard>
    );
  }
  return (
    <>
      {groups.map((g) => (
        <ReportCard key={g.dept} title={ANNUAL.groupTitle(g.dept, g.count)}>
          <ul className={styles.list}>
            {g.candidates.map((c) => (
              <li key={c.gid} className={styles.item}>
                <p className={styles.head}>{ANNUAL.rankScore(c.rank, c.score)}</p>
                <p className={styles.place}>
                  {c.address ? <span>{`${ANNUAL.refAddress}: ${c.address}`}</span> : <span>{`격자 ${c.gid}`}</span>}
                  {c.landmark ? <span className={styles.landmark}>{c.landmark}</span> : null}
                </p>
                {c.evidence.length ? (
                  <p className={styles.line}>
                    <span className={styles.label}>{ANNUAL.evidenceLabel}</span>
                    {c.evidence.join(' · ')}
                  </p>
                ) : null}
                {c.requestText ? (
                  <p className={styles.line}>
                    <span className={styles.label}>{ANNUAL.requestLabel}</span>
                    {c.requestText}
                  </p>
                ) : null}
                <p className={styles.meta}>{`${ANNUAL.dataAsOf}: ${c.dataAsOf || ANNUAL.dataAsOfUnknown}`}</p>
              </li>
            ))}
          </ul>
        </ReportCard>
      ))}
    </>
  );
}
