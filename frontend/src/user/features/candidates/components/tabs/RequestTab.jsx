import { useState } from 'react';
import Button from '../../../../components/Button.jsx';
import Icon from '../../../../components/Icon.jsx';
import Tag from '../../../../components/Tag.jsx';
import { DRAWER } from '../../copy.js';
import styles from './Tabs.module.css';

/** ⑥ 요청안 (US-03 6-1). 우선 점검 대상에만 보인다. 자동 발송은 없다. */
export default function RequestTab({ detail, onGoTab }) {
  const d = detail;
  const [copied, setCopied] = useState(false);

  if (!d.dept) {
    return (
      <section>
        <h3 className={styles.h}>{DRAWER.requestTitle}</h3>
        <div className={styles.content}>
          <p className={styles.err} role="alert">
            {DRAWER.needDept}
          </p>
          <div>
            <Button onClick={() => onGoTab(3)}>{DRAWER.pickDept}</Button>
          </div>
        </div>
      </section>
    );
  }

  const years = [...new Set(d.evidence.map((e) => `${e.basisYear}년`))].join(', ') || '기준일 미확인';
  const text = DRAWER.requestText(d.dept.name, d.request?.content ?? '현장 확인', d.landmark, d.address, d.topEvidence.join(', '), years);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <section>
      <h3 className={styles.h}>{DRAWER.requestTitle}</h3>
      <p className={styles.sub}>{DRAWER.requestSub}</p>
      <div className={styles.content}>
        <p className={styles.reqText}>
          <Icon name="sparkle" size={16} className={styles.sparkle} />
          <span>{text}</span>
        </p>
        <div className={styles.right} style={{ justifyContent: 'flex-end' }}>
          {copied ? (
            <span role="status" className={styles.muted}>
              {DRAWER.requestCopied}
            </span>
          ) : null}
          <Button variant="soft" onClick={copy}>
            {DRAWER.requestCopy}
          </Button>
        </div>

        <h4 className={styles.h} style={{ fontSize: 'var(--fs-body-lg)' }}>
          {DRAWER.actionTitle}
        </h4>
        <ul className={styles.list}>
          {d.problems.map((p) => (
            <li key={p.key} className={styles.actionRow}>
              <Icon name="sparkle" size={16} className={styles.sparkle} />
              <span>{p.sentence}</span>
              <span aria-hidden="true">→</span>
              {p.dept ? (
                <span>{p.dept}</span>
              ) : (
                <Tag tone="mid" small>
                  {DRAWER.actionDeptCheck}
                </Tag>
              )}
              <span>{`· 근거: ${p.article || DRAWER.articlePending2}`}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
