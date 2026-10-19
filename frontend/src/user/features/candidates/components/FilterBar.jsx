import Button from '../../../components/Button.jsx';
import Tag from '../../../components/Tag.jsx';
import Icon from '../../../components/Icon.jsx';
import { RELIABILITY } from '../../../../shared/constants.js';
import { LIST } from '../copy.js';
import { activeTags, clearTag } from '../filters.js';
import styles from './FilterBar.module.css';

function ChipGroup({ label, options, value, onToggle }) {
  return (
    <div className={styles.group} role="group" aria-label={label}>
      <span className={styles.groupLabel}>{label}</span>
      <div className={styles.chips}>
        {options.map((o) => {
          const on = value.includes(o);
          return (
            <button key={o} type="button" className={`${styles.chip} ${on ? styles.chipOn : ''}`} aria-pressed={on} onClick={() => onToggle(o)}>
              {o}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/**
 * 2-1 필터. 표 카드 위 오른쪽의 '필터' 버튼을 누르면 아래로 펼쳐진다.
 * 결정 상태는 KPI 카드가, 우선 확인 조건은 시스템 제안 얼럿이 맡는다.
 */
export default function FilterBar({ filters, setFilters, city, obstacleOptions, open, setOpen, onCompare }) {
  const tags = activeTags(filters);
  const toggle = (key) => (v) =>
    setFilters({ ...filters, [key]: filters[key].includes(v) ? filters[key].filter((x) => x !== v) : [...filters[key], v] });

  return (
    <section className={styles.bar} aria-label="점검 후보 필터">
      <div className={styles.row}>
        {city ? (
          <Button variant="soft" className={styles.btn} onClick={onCompare}>
            {LIST.compareButton}
          </Button>
        ) : null}
        <Button variant="soft" className={styles.btn} aria-expanded={open} aria-controls="filter-panel" onClick={() => setOpen(!open)}>
          <Icon name="filter" size={16} />
          {LIST.filterButton}
          {tags.length > 0 ? <span className={styles.count}>{tags.length}</span> : null}
        </Button>
      </div>

      {open ? (
        <div id="filter-panel" className={styles.panel} role="group" aria-label={LIST.filterPanelLabel}>
          <ChipGroup label={LIST.obstacleLabel} options={obstacleOptions} value={filters.obstacles} onToggle={toggle('obstacles')} />
          <ChipGroup label={LIST.reliabilityLabel} options={RELIABILITY} value={filters.reliability} onToggle={toggle('reliability')} />
          <ChipGroup label={LIST.zoneLabel} options={LIST.zoneOptions} value={filters.zone} onToggle={toggle('zone')} />
          <ChipGroup label={LIST.complaintLabel} options={LIST.complaintOptions} value={filters.complaint} onToggle={toggle('complaint')} />
        </div>
      ) : null}

      {tags.length ? (
        <ul className={styles.tags} aria-label="고른 필터">
          {tags.map((t) => (
            <li key={t.key}>
              <Tag tone="info" onRemove={() => setFilters(clearTag(filters, t))} removeLabel={`${t.text} 필터 지우기`}>
                {t.text}
              </Tag>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
