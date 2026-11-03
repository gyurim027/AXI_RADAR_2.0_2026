import { useState } from 'react';
import Button from '../../../../components/Button.jsx';
import { InfoHelp } from '../../../../components/FormControls.jsx';
import DecisionReasonModal from '../DecisionReasonModal.jsx';
import { DECISION } from '../../../../../shared/constants.js';
import { DRAWER } from '../../copy.js';
import styles from './Tabs.module.css';

/** ⑤ 결정 기록 (US-03 5-1 결정 고르기, 5-3 결정 이력). 점검 대상을 확정한 뒤에는 고칠 수 없다. */
export default function DecisionTab({ detail, onChanged, onGoTab, onClose }) {
  const d = detail;
  const [choice, setChoice] = useState(null); // 사유 입력 창을 연 결정

  const done = async (decision) => {
    setChoice(null);
    await onChanged();
    // 우선 점검 대상이면 담당 부서가 정해졌는지 보고 ⑥ 요청안 또는 ③ 담당 부서로 간다 (U-31~U-34)
    if (decision === DECISION.TARGET) onGoTab(d.dept ? 6 : 3);
    else onClose();
  };

  return (
    <section>
      {d.canDecide ? (
        <div className={styles.content}>
          <p className={styles.sub}>{DRAWER.decisionSub}</p>
          <div className={styles.choices} role="group" aria-label={DRAWER.decisionTitle}>
            {DRAWER.decisionChoices.map((c) => (
              <Button key={c} variant={c === d.decision ? 'primary' : 'soft'} aria-pressed={c === d.decision} onClick={() => setChoice(c)}>
                {c}
              </Button>
            ))}
            <InfoHelp label={DRAWER.decisionHelpAllLabel}>
              {DRAWER.decisionChoices.map((c) => (
                <span key={c} className={styles.helpLine}>
                  <b>{c}</b> {DRAWER.decisionHelp[c]}
                </span>
              ))}
            </InfoHelp>
          </div>
        </div>
      ) : null}

      <div className={styles.content}>
        <h4 className={styles.h} style={{ fontSize: 'var(--fs-body-lg)' }}>
          {DRAWER.historyTitle}
        </h4>
        <ul className={styles.hist}>
          {d.history.map((h, i) => (
            <li key={`${h.date}-${i}`} className={styles.histRow}>
              {DRAWER.historyRow(h.date, h.from, h.to, h.org)}
            </li>
          ))}
        </ul>
      </div>

      {choice ? <DecisionReasonModal runId={d.run.id} gid={d.gid} decision={choice} onClose={() => setChoice(null)} onSaved={() => done(choice)} /> : null}
    </section>
  );
}
