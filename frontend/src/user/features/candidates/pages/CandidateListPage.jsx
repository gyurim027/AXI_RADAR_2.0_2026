import { useCallback, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getCandidateDetail, getGuCompare, listCandidates } from '../../../../api/candidates.js';
import { useAsync } from '../../../../shared/hooks/useAsync.js';
import { useAuth } from '../../../../app/providers/AuthProvider.jsx';
import { useRun } from '../../../../app/providers/RunProvider.jsx';
import { ALL_GU, PAGE_SIZE, ROLE, RUN_STATUS } from '../../../../shared/constants.js';
import { COMMON } from '../../../../shared/copy/common.js';
import PageHeader from '../../../components/PageHeader.jsx';
import PageFooterNote from '../../../components/PageFooterNote.jsx';
import Pagination from '../../../components/Pagination.jsx';
import { EmptyState, ErrorState, SkeletonRows, SkeletonBlock } from '../../../components/States.jsx';
import { LIST } from '../copy.js';
import { EMPTY_FILTERS, activeTags, applyFilters, isPriority, sortRows } from '../filters.js';
import BottomBar from '../components/BottomBar.jsx';
import CandidateMap from '../components/CandidateMap.jsx';
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

  const list = useAsync(() => listCandidates({ runId: run.id, gu }), [run.id, gu, user.id, version]);
  const detail = useAsync(
    () => (selectedId ? getCandidateDetail({ runId: run.id, gid: selectedId }) : Promise.resolve(null)),
    [run.id, selectedId, user.id, version],
  );
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
      bar = { message: LIST.barCity, button: LIST.barCityButton, variant: 'soft' };
    }
  }

  const scope = city ? (gu === ALL_GU ? '3개 구 전체' : gu) : user.gu;
  const clearAll = () => changeFilters(EMPTY_FILTERS);

  return (
    <div className={styles.split}>
      <div className={styles.left} ref={scrollRef}>
        <div className={styles.leftInner}>
          <PageHeader eyebrow={LIST.eyebrow(scope)} title={LIST.title} subtitle={city ? LIST.subtitleCity : LIST.subtitleDistrict} />

          {data ? <KpiCards counts={data.counts} active={filters.decision} onPick={(d) => changeFilters({ ...filters, decision: d })} /> : null}

          <div className={styles.filterRow}>
            <FilterBar
              filters={filters}
              setFilters={changeFilters}
              city={city}
              obstacleOptions={data?.obstacleOptions ?? []}
              open={filterOpen}
              setOpen={setFilterOpen}
              onCompare={() => setCompare(true)}
            />
          </div>

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
                  conditionMap={conditionMap}
                  onDecide={(r, d) => setDeciding({ gid: r.gid, decision: d })}
                  selectedId={selectedId}
                  onSelect={select}
                  sort={sort}
                  onSort={onSort}
                  emptyContent={
                    <EmptyState
                      text={COMMON.emptyList}
                      hint={filters.decision || filters.priorityOnly || tags.length ? COMMON.emptyListHint : undefined}
                      actionLabel={filters.decision || filters.priorityOnly || tags.length ? COMMON.emptyListClear : undefined}
                      onAction={clearAll}
                    />
                  }
                />
              )}
            </div>
            {!compare && data ? <Pagination page={curPage} total={pageCount} onChange={setPage} /> : null}
          </section>

          {data && unrated.length > 0 ? (
            <UnratedPanel rows={unrated} open={unratedOpen} onToggle={() => setUnratedOpen((o) => !o)} selectedId={selectedId} onSelect={select} />
          ) : null}

          <PageFooterNote />
        </div>

        {bar ? (
          <BottomBar scrollRef={scrollRef} message={bar.message} buttonLabel={bar.button} buttonVariant={bar.variant} onButton={() => setConfirmOpen(true)} />
        ) : null}
      </div>

      <div className={styles.mapCol}>
        <CandidateMap
          items={filtered}
          unrated={unrated}
          boundaries={data?.guBoundaries}
          ownGu={district ? user.gu : null}
          selectedId={selectedId}
          onSelect={select}
          fitKey={`${run.id}:${gu}:${data ? 'ready' : 'wait'}`}
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
        {drawerOpen && selectedRow ? (
          <DetailDrawer
            row={selectedRow}
            detail={detail.data}
            loading={detail.loading}
            failed={detail.failed}
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
          onClose={() => setConfirmOpen(false)}
          onConfirmed={() => {
            onChanged();
            reloadRuns();
          }}
        />
      ) : null}
    </div>
  );
}
