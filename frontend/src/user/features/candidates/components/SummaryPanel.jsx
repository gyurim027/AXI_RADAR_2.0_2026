import Button from '../../../components/Button.jsx';
import Icon from '../../../components/Icon.jsx';
import Tag from '../../../components/Tag.jsx';
import { SkeletonBlock } from '../../../components/States.jsx';
import { SUMMARY } from '../copy.js';
import styles from './SummaryPanel.module.css';

/**
 * 5-1 근거 팝업(US-02 요약 패널). 격자를 누르면 지도 위쪽에 뜬다. ×를 누르면 닫히고 목록 선택이 풀린다.
 * 설명문은 문장 틀로 만들고 AI가 다듬는다(AI-07). 다듬은 숫자가 원래와 다르면 원래 문장을 쓴다.
 */
export default function SummaryPanel({ row, detail, loading, onClose, onDetail }) {
  return (
    <section className={styles.panel} aria-label="후보 요약">
      <div className={styles.head}>
        <div className={styles.meta}>
          <Tag tone="neutral" small>
            {row.decision}
          </Tag>
          {row.rank != null ? <span className={`${styles.rank} num`}>{SUMMARY.rank(row.rank)}</span> : null}
        </div>
        <button type="button" className={styles.close} onClick={onClose} aria-label={SUMMARY.close}>
          <Icon name="close" size={22} />
        </button>
      </div>
      <h2 className={styles.title}>{SUMMARY.title(row.address, row.landmark)}</h2>

      {loading || !detail ? (
        <div className={styles.skel}>
          <SkeletonBlock />
        </div>
      ) : (
        <>
          {detail.explanation ? (
            <p className={styles.explain}>
              <Icon name="sparkle" size={16} className={styles.sparkle} />
              <span className={styles.clamp}>{detail.explanation}</span>
            </p>
          ) : (
            <p className={styles.fail} role="alert">
              {SUMMARY.explanationFailed}
            </p>
          )}
          <h3 className={styles.sub}>{SUMMARY.evidenceTitle}</h3>
          <ul className={styles.dots}>
            {detail.topEvidence.map((e, i) => (
              <li key={`${i}-${e}`}>{e}</li>
            ))}
          </ul>
          <h3 className={styles.sub}>{SUMMARY.deptTitle}</h3>
          {detail.dept ? (
            <p>{`${detail.dept.name} · ${detail.dept.status}`}</p>
          ) : (
            <p>
              <Tag tone="mid" small>
                {SUMMARY.deptUndecided}
              </Tag>
            </p>
          )}
          <div className={styles.actions}>
            <Button variant="soft" onClick={onDetail}>
              {SUMMARY.detailButton}
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
