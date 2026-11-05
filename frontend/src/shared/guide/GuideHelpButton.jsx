import { useSyncExternalStore } from 'react';
import { GUIDE_COPY } from './guideConfig.js';
import { getAvailable, requestGuide, subscribe } from './guideStore.js';
import styles from './GuideTour.module.css';

/** 상단 메뉴의 `?`. 지금 화면에 안내할 항목이 있을 때만 보이고, 누르면 안내를 처음부터 다시 보여 준다. */
export default function GuideHelpButton() {
  const available = useSyncExternalStore(subscribe, getAvailable);
  if (!available) return null;
  return (
    <button type="button" className={styles.help} aria-label={GUIDE_COPY.helpLabel} title={GUIDE_COPY.helpLabel} onClick={requestGuide}>
      ?
    </button>
  );
}
