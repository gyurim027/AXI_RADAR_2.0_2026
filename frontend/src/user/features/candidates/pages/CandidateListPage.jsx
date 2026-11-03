import { useCallback, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getCandidateDetail, getConfirmSummary, getGuCompare, listCandidates, logComplaintPointView } from '../../../../api/candidates.js';
import { useAsync } from '../../../../shared/hooks/useAsync.js';
import { useAuth } from '../../../../app/providers/AuthProvider.jsx';
import { useRun } from '../../../../app/providers/RunProvider.jsx';
import { ALL_GU, CONFIRM_DEADLINES, PAGE_SIZE, ROLE, RUN_STATUS } from '../../../../shared/constants.js';
import { dataYear, runYear } from '../../../../shared/utils/format.js';
import { COMMON } from '../../../../shared/copy/common.js';
import PageHeader from '../../../components/PageHeader.jsx';
import PageFooterNote from '../../../components/PageFooterNote.jsx';
import Pagination from '../../../components/Pagination.jsx';
import { EmptyState, ErrorState, SkeletonRows, SkeletonBlock } from '../../../components/States.jsx';
import { LIST } from '../copy.js';
import { EMPTY_FILTERS, activeTags, applyFilters, isPriority, sortRows } from '../filters.js';
import BottomBar from '../components/BottomBar.jsx';
import SplitHandle from '../components/SplitHandle.jsx';
import useSplit from '../useSplit.js';
import CandidateMap from '../components/CandidateMap.jsx';
import StackTabs from '../components/StackTabs.jsx';
import { prefersReducedMotion } from '../components/mapUtils.js';
import ConfirmModal from '../components/ConfirmModal.jsx';
import DecisionReasonModal from '../components/DecisionReasonModal.jsx';
import DetailDrawer from '../components/DetailDrawer.jsx';
import FilterBar from '../components/FilterBar.jsx';
import GuCompare from '../components/GuCompare.jsx';
import KpiCards from '../components/KpiCards.jsx';
import PriorityAlert from '../components/PriorityAlert.jsx';
import RankTable from '../components/RankTable.jsx';
import SummaryPanel from '../components/SummaryPanel.jsx';
import UnratedPanel from '../components/UnratedPanel.jsx';
import Button from '../../../components/Button.jsx';
import drawerStyles from '../components/DetailDrawer.module.css';
import styles from './CandidateListPage.module.css';

/** 회차를 바꾸면 화면 상태(선택, 필터, 쪽)를 새로 시작한다 */
export default function CandidateListRoute() {
  const { run } = useRun();
  return <CandidateListPage key={run.id} />;
}

/**
 * 점검 후보 화면 (와이어프레임 261019)
 * 왼쪽 열(스크롤): 머리 → 1 KPI → 2 점검 후보 표(2-1 필터, 2-2 시스템 제안, 2-3 표, 2-4 쪽 번호) → 3 평가하지 못한 구역 → 안내 → 4 바텀 바
 * 오른쪽: 5 지도(5-1 근거 팝업, 5-2 격자, 5-3 줌, 5-4 범례). 근거 자세히 보기는 서랍으로 지도 열을 덮는다.
 */
function CandidateListPage() {
  const { user } = useAuth();
  const { run, gu, reloadRuns } = useRun();
  const city = user.role === ROLE.CITY;
  const district = user.role === ROLE.DISTRICT;

  const [params, setParams] = useSearchParams();
  const selectedId = params.get('sel');
  const drawerOpen = params.get('detail') === '1' && !!selectedId;
  const tab = Number(params.get('tab')) || 1;

  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [filterOpen, setFilterOpen] = useState(false);
  const [sort, setSort] = useState({ key: 'rank', dir: 'asc' });
  const [page, setPage] = useState(1);
  const [compare, setCompare] = useState(false);
  const [unratedOpen, setUnratedOpen] = useState(false);
  const [version, setVersion] = useState(0);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deciding, setDeciding] = useState(null); // { gid, decision } 표에서 결정을 바꾸는 중
  const scrollRef = useRef(null);
  const mapColRef = useRef(null);
  const splitRef = useRef(null);
  const split = useSplit();
  const stackSections = useMemo(
    () => [
      { key: 'table', label: LIST.stackTable, ref: scrollRef },
      { key: 'map', label: LIST.stackMap, ref: mapColRef },
    ],
    [],
  );

  const list = useAsync(() => listCandidates({ runId: run.id, gu }), [run.id, gu, user.id, version]);
  const detail = useAsync(
    () => (selectedId ? getCandidateDetail({ runId: run.id, gid: selectedId }) : Promise.resolve(null)),
    [run.id, selectedId, user.id, version],
  );
  // 시 도로과 첫 화면의 '확정 현황: 2/3개 구' 줄 (5-2 ①)
  const guStatus = useAsync(() => (city ? getConfirmSummary({ runId: run.id }) : Promise.resolve(null)), [city, run.id, version]);
  const cmp = useAsync(() => (compare && city ? getGuCompare({ runId: run.id }) : Promise.resolve(null)), [compare, city, run.id, version]);

  const data = list.data;
  const rows = useMemo(() => data?.items ?? [], [data]);
  const unrated = useMemo(() => data?.unrated ?? [], [data]);
  const conditions = useMemo(() => data?.conditions ?? [], [data]);
  const conditionMap = useMemo(() => Object.fromEntries(conditions.map((c) => [c.id, c])), [conditions]);
  const knownIds = useMemo(() => new Set(conditions.map((c) => c.id)), [conditions]);

  // KPI(결정 상태)와 필터를 거친 뒤, 시스템 제안 얼럿(우선 확인 조건)을 더한다. 둘은 함께 적용된다.
  const beforePriority = useMemo(() => applyFilters(rows, { ...filters, priorityOnly: false }), [rows, filters]);
  const priorityCount = useMemo(() => beforePriority.filter((r) => isPriority(r, knownIds)).length, [beforePriority, knownIds]);
  const filtered = useMemo(() => (filters.priorityOnly ? beforePriority.filter((r) => isPriority(r, knownIds)) : beforePriority), [beforePriority, filters.priorityOnly, knownIds]);
  const sorted = useMemo(() => sortRows(filtered, sort), [filtered, sort]);
  const pageCount = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const curPage = Math.min(page, pageCount);
  const pageRows = sorted.slice((curPage - 1) * PAGE_SIZE, curPage * PAGE_SIZE);

  const selectedRow = useMemo(() => [...rows, ...unrated].find((r) => r.gid === selectedId) || null, [rows, unrated, selectedId]);

  const setSearch = useCallback(
    (next) => {
      const p = new URLSearchParams(params);
      Object.entries(next).forEach(([k, v]) => (v == null ? p.delete(k) : p.set(k, v)));
      setParams(p, { replace: true });
    },
    [params, setParams],
  );

  const select = useCallback(
    (gid) => {
      const idx = sorted.findIndex((r) => r.gid === gid);
      if (idx >= 0) setPage(Math.floor(idx / PAGE_SIZE) + 1); // 지도에서 고르면 표의 그 행이 있는 쪽으로 간다
      setSearch({ sel: gid, detail: null, tab: null });
      // 태블릿 폭에서는 지도가 표 아래에 있어, 구역을 고르면 지도로 내려가 보여 준다
      if (window.innerWidth < 1100) mapColRef.current?.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' });
      // 그 구의 민원 점을 처음 볼 때 접속 기록을 남긴다 (로그인 한 번에 구마다 한 줄, I-04)
      const row = sorted[idx];
      if (row) logComplaintPointView({ gu: row.gu, hasPoints: (row.complaintPoints?.length || 0) > 0 }).catch(() => {});
    },
    [sorted, setSearch],
  );
  const closeSummary = () => setSearch({ sel: null, detail: null, tab: null });
  const openDetail = () => setSearch({ detail: '1', tab: '1' });
  const closeDetail = useCallback(() => setSearch({ detail: null, tab: null }), [setSearch]);
  const setTab = (t) => setSearch({ tab: String(t) });
  const onChanged = useCallback(() => setVersion((v) => v + 1), []);

  const idx = sorted.findIndex((r) => r.gid === selectedId);
  const prev = idx > 0 ? sorted[idx - 1] : null;
  const next = idx >= 0 && idx < sorted.length - 1 ? sorted[idx + 1] : null;
  const goTo = (r) => {
    setPage(Math.floor(sorted.indexOf(r) / PAGE_SIZE) + 1);
    setSearch({ sel: r.gid });
  };

  const onSort = (key) => {
    setPage(1);
    setSort((s) => (s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: key === 'score' ? 'desc' : 'asc' }));
  };
  const changeFilters = (f) => {
    setFilters(f);
    setPage(1);
  };
  const tags = activeTags(filters);

  const reviewing = run.status === RUN_STATUS.REVIEW;
  const myConfirm = data?.myConfirm;
  const canDecide = !!data?.canDecide;

  // 4 바텀 바: 도로관리팀은 결정 완료 여부에 따라 두 글, 확정한 뒤에는 완료 문구, 시 도로과는 확정 현황. 확정·참고 회차에는 없다.
  let bar = null;
  if (data) {
    if (user.readOnly && district) {
      bar = null; // 보기 전용: 확정 버튼과 안내를 숨긴다 (AD-00 4-1)
    } else if (district && reviewing && myConfirm && !myConfirm.done) {
      bar =
        data.counts.none > 0
          ? { message: LIST.barUndecided(data.counts.none), button: LIST.barButton, variant: 'neutral' }
          : { message: LIST.barDecided, button: LIST.barButton, variant: 'primary' };
    } else if (district && myConfirm?.done && run.status !== RUN_STATUS.REF) {
      bar = { message: LIST.barDone(user.gu, myConfirm.date) };
    } else if (city && (reviewing || run.status === RUN_STATUS.FINAL)) {
      bar = { message: '', button: LIST.barCityButton, variant: 'soft' }; // 시 도로과는 버튼만 보인다 (US-01 1-7)
    }
  }

  // 첫 화면 한 줄 안내 (5-1 ①, 5-2 ①). 도로관리팀은 결정 전 건수와 마감일, 시 도로과는 구 확정 현황이다.
  const deadline = CONFIRM_DEADLINES[runYear(run.name)];
  let guide = null;
  if (data && !user.readOnly && district && reviewing && myConfirm && !myConfirm.done) {
    guide = <p className={styles.guide}>{LIST.guideDistrict(data.counts.none, deadline)}</p>;
  } else if (data && city && (reviewing || run.status === RUN_STATUS.FINAL) && guStatus.data) {
    const sts = guStatus.data.guStatuses;
    guide = (
      <p className={styles.guide}>
        <button type="button" className={styles.guideBtn} onClick={() => setConfirmOpen(true)}>
          {LIST.guideCity(sts.filter((x) => x.done).length, sts.length)}
        </button>
      </p>
    );
  }

  const scope = city ? (gu === ALL_GU ? '3개 구 전체' : gu) : user.gu;
  const clearAll = () => changeFilters(EMPTY_FILTERS);

  return (
    <div
      className={`${styles.split} ${split.animating ? styles.animate : ''} ${split.dragging ? styles.dragging : ''}`}
      style={split.style}
      ref={splitRef}
    >
      {split.wide ? null : <StackTabs label={LIST.stackTabsLabel} sections={stackSections} containerRef={splitRef} />}
      <div className={`${styles.left} ${split.tableHidden ? styles.collapsed : ''}`} ref={scrollRef} inert={split.tableHidden}>
        <div className={styles.leftInner}>
          <PageHeader compact eyebrow={run.dataRange ? `${LIST.eyebrow(scope)} · ${LIST.dataBasis(dataYear(run.dataRange))}` : LIST.eyebrow(scope)} title={LIST.title} subtitle={city ? LIST.subtitleCity : LIST.subtitleDistrict}>
            {guide}
          </PageHeader>

          {data ? <KpiCards counts={data.counts} active={filters.decision} onPick={(d) => changeFilters({ ...filters, decision: d })} /> : null}

          <div className={styles.filterRow}>
            <FilterBar
              filters={filters}
              setFilters={changeFilters}
              city={city}
              obstacleOptions={data?.obstacleOptions ?? []}
              unavailable={data?.unavailableFilters ?? []}
              open={filterOpen}
              setOpen={setFilterOpen}
              onCompare={() => setCompare(true)}
            />
          </div>

          {city && gu === ALL_GU && data?.noGuCount > 0 ? (
            <p className={styles.noGuNote} role="status">
              {LIST.noGuNote(data.noGuCount)}
            </p>
          ) : null}

          <section className={styles.tableCard} aria-label="점검 후보 목록">
            {!compare && data && conditions.length > 0 && (priorityCount > 0 || filters.priorityOnly) ? (
              <PriorityAlert
                count={priorityCount}
                active={filters.priorityOnly}
                onApply={() => changeFilters({ ...filters, priorityOnly: true })}
                onClear={() => changeFilters({ ...filters, priorityOnly: false })}
              />
            ) : null}
            <div className={styles.scroll}>
              {list.failed ? (
                <ErrorState areaName="점검 후보 목록" onRetry={list.reload} />
              ) : list.loading && !data ? (
                list.showSkeleton ? <SkeletonRows rows={8} /> : null
              ) : compare && city ? (
                cmp.failed ? (
                  <ErrorState areaName="구별 비교" onRetry={cmp.reload} />
                ) : cmp.data ? (
                  <GuCompare rows={cmp.data.rows} onBack={() => setCompare(false)} />
                ) : cmp.showSkeleton ? (
                  <SkeletonRows rows={4} />
                ) : null
              ) : (
                <RankTable
                  rows={pageRows}
                  city={city}
                  canDecide={canDecide}
                  onDecide={(r, d) => setDeciding({ gid: r.gid, decision: d })}
                  conditionMap={conditionMap}
                  selectedId={selectedId}
                  onSelect={select}
                  sort={sort}
                  onSort={onSort}
                  emptyContent={
                    <EmptyState
                      text={rows.length === 0 ? COMMON.noCandidates : COMMON.emptyList}
                      hint={rows.length === 0 ? COMMON.noCandidatesHint : filters.decision || filters.priorityOnly || tags.length ? COMMON.emptyListHint : undefined}
                      actionLabel={rows.length > 0 && (filters.decision || filters.priorityOnly || tags.length) ? COMMON.emptyListClear : undefined}
                      onAction={clearAll}
                    />
                  }
                />
              )}
            </div>
            {!compare && data ? <Pagination page={curPage} total={pageCount} onChange={setPage} /> : null}
          </section>

          {data && unrated.length > 0 ? (
            <UnratedPanel rows={unrated} city={city} open={unratedOpen} onToggle={() => setUnratedOpen((o) => !o)} selectedId={selectedId} onSelect={select} />
          ) : null}

          <PageFooterNote />
        </div>

        {bar ? (
          <BottomBar scrollRef={scrollRef} message={bar.message} buttonLabel={bar.button} buttonVariant={bar.variant} onButton={() => setConfirmOpen(true)} />
        ) : null}
      </div>

      {split.wide ? <SplitHandle state={split.state} onChange={split.change} onDragState={split.setDragging} containerRef={splitRef} /> : null}

      <div className={`${styles.mapCol} ${split.mapHidden ? styles.collapsed : ''}`} ref={mapColRef} inert={split.mapHidden}>
        <CandidateMap
          items={filtered}
          unrated={unrated}
          boundaries={data?.guBoundaries}
          ownGu={district ? user.gu : null}
          selectedId={selectedId}
          onSelect={select}
          fitKey={`${run.id}:${gu}:${data ? 'ready' : 'wait'}`}
          cooperative={!split.wide}
        >
          {list.failed ? (
            <div className={styles.mapMsg}>
              <ErrorState areaName="점검 후보 지도" onRetry={list.reload} />
            </div>
          ) : list.loading && !data && list.showSkeleton ? (
            <div className={styles.mapMsg}>
              <SkeletonBlock />
            </div>
          ) : null}
          {selectedRow && !drawerOpen ? (
            <SummaryPanel row={selectedRow} detail={detail.data} loading={detail.loading} onClose={closeSummary} onDetail={openDetail} />
          ) : null}
        </CandidateMap>
        {drawerOpen && !selectedRow && detail.failed && ['forbidden', 'notFound'].includes(detail.error?.code) ? (
          // 다른 구 자료이거나 없는 후보 주소를 직접 열었을 때 (ERR-14·42)
          <aside className={drawerStyles.drawer} aria-label="후보 상세">
            <EmptyState text={detail.error.code === 'forbidden' ? COMMON.forbiddenGu : COMMON.notFoundCandidate}>
              <Button variant="soft" onClick={closeSummary}>
                {COMMON.backToList}
              </Button>
            </EmptyState>
          </aside>
        ) : null}
        {drawerOpen && selectedRow ? (
          <DetailDrawer
            row={selectedRow}
            detail={detail.data}
            loading={detail.loading}
            failed={detail.failed}
            errorCode={detail.error?.code}
            onRetry={detail.reload}
            tab={tab}
            setTab={setTab}
            onClose={closeDetail}
            onPrev={prev ? () => goTo(prev) : null}
            onNext={next ? () => goTo(next) : null}
            onChanged={onChanged}
            onGoTab={setTab}
          />
        ) : null}
      </div>

      {deciding ? (
        <DecisionReasonModal
          runId={run.id}
          gid={deciding.gid}
          decision={deciding.decision}
          onClose={() => setDeciding(null)}
          onFailed={onChanged}
          onSaved={() => {
            setDeciding(null);
            onChanged();
          }}
        />
      ) : null}

      {confirmOpen ? (
        <ConfirmModal
          runId={run.id}
          role={user.role}
          finalized={run.status === RUN_STATUS.FINAL}
          onClose={() => setConfirmOpen(false)}
          onFailed={onChanged}
          onConfirmed={() => {
            onChanged();
            reloadRuns();
          }}
        />
      ) : null}
    </div>
  );
}
