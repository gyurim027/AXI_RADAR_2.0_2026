import { useState } from 'react';
import Tag from '../../../../components/Tag.jsx';
import Card from '../../../../components/Card.jsx';
import { SelectField } from '../../../../components/FormControls.jsx';
import { setDept } from '../../../../../api/candidates.js';
import { DEPT_STATUS } from '../../../../../shared/constants.js';
import { DRAWER } from '../../copy.js';
import styles from './Tabs.module.css';

/** ③ 담당 부서 (US-03 3-1). 담당 미정이거나 확인 필요일 때만 도로관리팀이 직접 고른다. 고르면 변경 기록에 남는다. */
export default function DeptTab({ detail, onChanged }) {
  const d = detail;
  const [error, setError] = useState('');
  const needsPick = d.canPickDept && (!d.dept || d.dept.status === DEPT_STATUS.CHECK);

  const pick = async (name) => {
    if (!name) return;
    try {
      await setDept({ runId: d.run.id, gid: d.gid, deptName: name });
      setError('');
      onChanged();
    } catch {
      setError('담당 부서를 정하지 못했습니다. 다시 시도해 주세요.');
    }
  };

  return (
    <section>
      <p className={styles.sub}>{d.canPickDept ? DRAWER.deptSubDistrict : DRAWER.deptSubCity}</p>
      <div className={styles.content}>
        <Card title={DRAWER.deptTitle}>
        {d.dept ? (
          <p>{`${d.dept.name} · ${d.dept.contact} · ${d.dept.status}`}</p>
        ) : (
          <p>
            <Tag tone="mid">담당 미정</Tag>
          </p>
        )}
        <p className={styles.muted}>{DRAWER.deptReason(d.deptReason)}</p>
        {needsPick ? (
          <SelectField
            inline={false}
            label={DRAWER.deptSelectLabel}
            id="dept-select"
            value=""
            onChange={pick}
            placeholder={DRAWER.deptSelectPlaceholder}
            options={d.deptOptions}
          />
        ) : null}
        {error ? (
          <p className={styles.err} role="alert">
            {error}
          </p>
        ) : null}
        </Card>
      </div>
    </section>
  );
}
