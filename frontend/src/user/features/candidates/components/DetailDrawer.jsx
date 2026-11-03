import { useEffect, useRef } from 'react';
import Button from '../../../components/Button.jsx';
import Icon from '../../../components/Icon.jsx';
import Tag from '../../../components/Tag.jsx';
import { COMMON } from '../../../../shared/copy/common.js';
import { EmptyState, ErrorState, SkeletonBlock } from '../../../components/States.jsx';
import { DRAWER } from '../copy.js';
import RankBasisTab from './tabs/RankBasisTab.jsx';
import ArticlesTab from './tabs/ArticlesTab.jsx';
import DeptTab from './tabs/DeptTab.jsx';
import LastYearTab from './tabs/LastYearTab.jsx';
import DecisionTab from './tabs/DecisionTab.jsx';
import RequestTab from './tabs/RequestTab.jsx';
import styles from './DetailDrawer.module.css';
import { placeLabel } from '../../../../shared/utils/format.js';

/** 탭 목록. ⑤는 검토 중 회차의 자기 구 후보에서만, ⑥은 우선 점검 대상으로 정한 자기 구 후보에서만 보인다 (US-03 0-1). */
export function visibleTabs(detail) {
  const tabs = [1, 2, 3, 4];
  if (detail?.showDecisionTab) tabs.push(5);
  if (detail?.showRequest) tabs.push(6);
  return tabs;
}

/**
 * US-03 후보 상세. 오른쪽 서랍이 지도 영역을 덮는다. 목록은 뒤에 그대로 남는다.
 * 머리와 탭 줄은 고정하고 탭 내용만 스크롤한다.
 */
export default function DetailDrawer({ row, detail, loading, failed, errorCode, onRetry, tab, setTab, onClose, onPrev, onNext, onChanged, onGoTab }) {
  const ref = useRef(null);
  const tabs = visibleTabs(detail);
  const current = tabs.includes(tab) ? tab : 1;

  useEffect(() => {
    ref.current?.focus();
  }, []);
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape' && !document.querySelector('[aria-modal="true"]')) onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const onTabKey = (e) => {
    const i = tabs.indexOf(current);
    if (e.key === 'ArrowRight') setTab(tabs[(i + 1) % tabs.length]);
    else if (e.key === 'ArrowLeft') setTab(tabs[(i - 1 + tabs.length) % tabs.length]);
    else return;
    e.preventDefault();
  };

  return (
    <aside ref={ref} className={styles.drawer} tabIndex={-1} aria-label="후보 상세">
      <div className={styles.head}>
        <div className={styles.titleRow}>
          <h2 className={styles.title}>{`${row.rank != null ? `${row.rank}위 · ` : ''}${placeLabel(row)}`}</h2>
          <button type="button" className={styles.close} onClick={onClose} aria-label={DRAWER.closeLabel}>
            <Icon name="close" size={20} />
          </button>
        </div>
        {row.address || row.landmark ? <p className={styles.locationNote}>{DRAWER.locationNote}</p> : null}
        <div className={styles.metaRow}>
          <Tag tone="neutral" small>
            {row.decision}
          </Tag>
          <div className={styles.pn}>
            {onPrev ? (
              <Button variant="soft" className={styles.pnBtn} onClick={onPrev}>
                {DRAWER.prev}
              </Button>
            ) : null}
            {onNext ? (
              <Button variant="soft" className={styles.pnBtn} onClick={onNext}>
                {DRAWER.next}
              </Button>
            ) : null}
          </div>
        </div>
        <div className={styles.tabs} role="tablist" aria-label="후보 상세 탭" onKeyDown={onTabKey}>
          {tabs.map((t) => (
            <button
              key={t}
              id={`drawer-tab-${t}`}
              type="button"
              role="tab"
              aria-selected={t === current}
              aria-controls="drawer-panel"
              tabIndex={t === current ? 0 : -1}
              className={`${styles.tab} ${t === current ? styles.tabOn : ''}`}
              onClick={() => setTab(t)}
            >
              {DRAWER.tabs[t]}
            </button>
          ))}
        </div>
      </div>

      <div id="drawer-panel" role="tabpanel" aria-labelledby={`drawer-tab-${current}`} className={styles.body}>
        {failed && (errorCode === 'forbidden' || errorCode === 'notFound') ? (
          // 접근할 수 없거나 없는 후보는 불러오기 실패가 아니라 안내로 쓴다 (ERR-14·42, POL-024)
          <EmptyState text={errorCode === 'forbidden' ? COMMON.forbiddenGu : COMMON.notFoundCandidate}>
            <Button variant="soft" onClick={onClose}>
              {COMMON.backToList}
            </Button>
          </EmptyState>
        ) : failed ? (
          <ErrorState areaName="후보 상세" onRetry={onRetry} />
        ) : loading && !detail ? (
          <SkeletonBlock />
        ) : detail ? (
          <>
            {current === 1 ? <RankBasisTab detail={detail} /> : null}
            {current === 2 ? <ArticlesTab detail={detail} /> : null}
            {current === 3 ? <DeptTab detail={detail} onChanged={onChanged} /> : null}
            {current === 4 ? <LastYearTab detail={detail} /> : null}
            {current === 5 ? <DecisionTab detail={detail} onChanged={onChanged} onGoTab={onGoTab} onClose={onClose} /> : null}
            {current === 6 ? <RequestTab detail={detail} onGoTab={onGoTab} /> : null}
          </>
        ) : null}
      </div>
    </aside>
  );
}
