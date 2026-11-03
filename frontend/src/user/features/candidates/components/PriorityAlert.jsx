import Button from '../../../components/Button.jsx';
import Icon from '../../../components/Icon.jsx';
import { InfoHelp } from '../../../components/FormControls.jsx';
import { LIST } from '../copy.js';
import styles from './PriorityAlert.module.css';

/**
 * 2-2 시스템 제안 얼럿. 우선 확인 조건에 해당하는 곳이 있다고 알린다.
 * '확인하기'를 누르면 표가 그 곳만 보인다(KPI 선택과 함께 적용). 누른 뒤에는 '전체 보기'로 되돌린다.
 * 넓으면 한 줄(제목, 설명, 버튼), 좁으면 제목 줄 오른쪽 위에 버튼, 그 아래에 설명이 놓인다.
 */
export default function PriorityAlert({ count, active, onApply, onClear }) {
  return (
    <div className={styles.wrap}>
      <div className={styles.box} role="region" aria-label={LIST.alertTitle}>
        <p className={styles.title}>
          <Icon name="info" size={16} />
          {LIST.alertTitle}
        </p>
        <p className={styles.body}>
          {active ? LIST.alertActiveText : LIST.alertText(count)}
          <InfoHelp label={LIST.conditionHelpLabel}>{LIST.conditionHelp}</InfoHelp>
        </p>
        <Button variant="soft" size="sm" className={styles.btn} onClick={active ? onClear : onApply}>
          {active ? LIST.alertActiveButton : LIST.alertButton}
        </Button>
      </div>
    </div>
  );
}
