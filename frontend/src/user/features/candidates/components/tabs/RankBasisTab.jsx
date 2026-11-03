import Tag from '../../../../components/Tag.jsx';
import Icon from '../../../../components/Icon.jsx';
import DataTable from '../../../../components/DataTable.jsx';
import { InfoHelp } from '../../../../components/FormControls.jsx';
import { COMMON } from '../../../../../shared/copy/common.js';
import { formatBasis } from '../../../../../shared/utils/format.js';
import { DRAWER, LIST } from '../../copy.js';
import MiniMap from '../MiniMap.jsx';
import styles from './Tabs.module.css';

const AXIS_LABEL = { 위험: '위험 조건' };
const H = DRAWER.evidenceHead;

/** ① 순위 근거 (US-03 1-1) + 민원 신호 (1-2) */
export default function RankBasisTab({ detail }) {
  const d = detail;
  const columns = [
    { key: 'field', header: H[0], width: 80, render: (e) => e.field },
    { key: 'item', header: H[1], width: 190, render: (e) => e.item },
    {
      key: 'value',
      header: H[2],
      width: 110,
      render: (e) => (
        <span className={styles.valueCell}>
          {e.value}
          {e.sidewalkHelp ? (
            <InfoHelp label={DRAWER.sidewalkHelpLabel}>{DRAWER.sidewalkHelp}</InfoHelp>
          ) : null}
        </span>
      ),
    },
    { key: 'pos', header: H[3], width: 120, align: 'right', render: (e) => (e.pos != null ? `상위 ${e.pos}%` : '-') },
    { key: 'ratio', header: H[4], width: 100, align: 'right', render: (e) => `${e.ratio}%` },
    {
      key: 'basis',
      header: H[5],
      width: 160,
      render: (e) => (
        <Tag tone={e.updateType === '1회성' ? 'mid' : 'gray'} small>
          {formatBasis(e.basisYear, e.updateType)}
        </Tag>
      ),
    },
    { key: 'source', header: H[6], width: 230, render: (e) => e.source },
  ];
  const axes = d.axes.map((a) => AXIS_LABEL[a] || a).join(' · ');
  const complaintAria = d.complaint.has
    ? COMMON.complaintSummary(d.complaint.total, d.complaint.types.map((t) => `${t.type} ${t.count}`).join(', '), d.complaint.recur)
    : undefined;

  return (
    <div className={styles.section}>
      <section className={styles.block}>
        <h3 className={styles.h}>{DRAWER.basisTitle}</h3>
        <p className={styles.sub}>{DRAWER.basisSub}</p>
        <div className={styles.content}>
          {d.score != null ? (
            <p className={`${styles.numbers} num`}>
              {DRAWER.scoreLine(d.score, d.cityPercent)}
              <InfoHelp label={DRAWER.scoreHelpLabel}>{DRAWER.scoreHelp}</InfoHelp>
            </p>
          ) : null}
          {d.conditions?.length ? (
            <div className={styles.tagRow}>
              {d.conditions.map((c) => (
                <span key={c.id} className={styles.choice}>
                  <Tag tone="info">{LIST.conditionTag(c.name)}</Tag>
                  <InfoHelp label={`${c.name} 반영 비율 보기`}>{LIST.conditionRatioHelp(c.name, c.ratio)}</InfoHelp>
                </span>
              ))}
            </div>
          ) : null}
          {d.conditionStates ? (
            <div className={styles.tagRow} aria-label={LIST.conditionStateTitle}>
              {d.conditionStates.map((c) => (
                <Tag key={c.id} tone={c.state === 'Y' ? 'info' : 'gray'} small>
                  {`${c.name} ${LIST.conditionState[c.state]}`}
                </Tag>
              ))}
              <InfoHelp label={LIST.conditionStateHelpLabel}>{LIST.conditionStateHelp}</InfoHelp>
            </div>
          ) : null}
          {axes ? <div className={styles.tagRow}><Tag tone="info">{DRAWER.axisTag(axes)}</Tag></div> : null}
          {d.explanation ? (
            <p className={styles.explain}>
              <Icon name="sparkle" size={16} className={styles.sparkle} />
              {d.explanation}
            </p>
          ) : (
            <p className={styles.fail}>설명문을 만들지 못했습니다. 아래 근거를 직접 확인해 주세요.</p>
          )}
          {d.topEvidence?.length ? (
            <>
              <p className={styles.keyTitle}>핵심 근거</p>
              <ul className={styles.keyList}>
                {d.topEvidence.map((e, i) => (
                  <li key={`${i}-${e}`}>{e}</li>
                ))}
              </ul>
            </>
          ) : null}
          {d.evidence.length ? (
            <div className={styles.tableWrap}>
              <DataTable caption="순위 근거" columns={columns} rows={d.evidence} getRowKey={(e) => `${e.field}-${e.item}`} minWidth={990} />
            </div>
          ) : (
            <p className={styles.muted}>{COMMON.noEvidence}</p>
          )}
          <div className={styles.tagRow}>
            {d.unrated.map((u) => (
              <Tag key={u.name} tone="gray">
                {DRAWER.unratedTag(u.name, u.reason)}
              </Tag>
            ))}
            {d.unrated.length ? <InfoHelp label={DRAWER.unratedHelpLabel}>{DRAWER.unratedHelp}</InfoHelp> : null}
            <Tag tone={d.reliability === '낮음' ? 'mid' : 'gray'}>{DRAWER.reliabilityTag(d.reliability, d.reliabilityReason)}</Tag>
            <InfoHelp label={DRAWER.reliabilityHelpLabel}>{DRAWER.reliabilityHelp}</InfoHelp>
          </div>
          <MiniMap bounds={d.bounds} points={d.points} tier={d.score >= 70 ? 'top' : d.score >= 50 ? 'mid' : 'rest'} />
        </div>
      </section>

      <section className={styles.block} aria-label={complaintAria}>
        <h3 className={styles.h}>{DRAWER.complaintTitle}</h3>
        <div className={styles.content}>
          {!d.complaint.has ? (
            <p className={styles.muted}>{DRAWER.complaintEmpty}</p>
          ) : (
            <>
              <p>{d.complaint.types.length ? DRAWER.complaintLine(d.complaint.types) : '민원 0건'}</p>
              {d.complaint.lowAccuracy > 0 ? <p className={styles.muted}>{DRAWER.complaintLowAccuracy(d.complaint.lowAccuracy)}</p> : null}
            </>
          )}
        </div>
      </section>
    </div>
  );
}
