import DataTable from '../../../components/DataTable.jsx';
import Tag, { Badge } from '../../../components/Tag.jsx';
import { COMMON } from '../../../../shared/copy/common.js';
import { LIST } from '../copy.js';
import DecisionMenu from './DecisionMenu.jsx';
import styles from './RankTable.module.css';
import { placeLabel } from '../../../../shared/utils/format.js';

const RELI_TONE = { 높음: 'low', 보통: 'neutral', 낮음: 'mid' };

/** 평가하지 못한 분야가 있는 후보에 회색 꼬리표를 붙인다. 조사 안 한 곳은 0으로 보이지 않는다 (CM-00 9번). */
export function UnratedTags({ row }) {
  if (!row.unratedCount) return null;
  return (
    <span className={styles.tags}>
      <Tag tone="gray" small>
        {COMMON.unratedTag(row.unratedCount, row.unratedNames)}
      </Tag>
      {row.notSurveyed.length ? (
        <Tag tone="gray" small>
          {COMMON.notSurveyedTag(row.notSurveyed.join(', '))}
        </Tag>
      ) : null}
    </span>
  );
}

// 열 폭(px). 머리는 한 줄이라 이름이 긴 열은 폭을 넓힌다 (와이어프레임 2-3). 남는 폭은 후보 열이 받는다.
function columnsFor({ city, canDecide, conditionMap, onDecide }) {
  const cols = [
    { key: 'rank', header: '순위', width: 64, sticky: true, sortable: true, align: 'right', render: (r) => <span className="num">{r.rank}</span> },
  ];
  if (city) cols.push({ key: 'gu', header: '구', width: 64, sticky: true, sortable: true, render: (r) => r.gu });
  cols.push(
    {
      key: 'address',
      header: LIST.candidateHead,
      width: 250,
      fill: true,
      sticky: true,
      sortable: true,
      render: (r) => (
        <span className={styles.cand}>
          <span className={styles.addr}>{r.address || (r.landmark ? '' : placeLabel(r))}</span>
          <span className={styles.landmark}>{r.landmark}</span>
          {/* 우선 확인 조건에 맞은 후보는 먼저 볼 이유를 꼬리표로 보인다. 반영 비율은 상세에 있다 (W-7) */}
          {r.conditions.filter((id) => conditionMap[id]).length > 0 ? (
            <span className={styles.tags}>
              {r.conditions
                .filter((id) => conditionMap[id])
                .map((id) => (
                  <Tag key={id} tone="info" small>
                    {LIST.conditionTag(conditionMap[id].name)}
                  </Tag>
                ))}
            </span>
          ) : null}
          <UnratedTags row={r} />
        </span>
      ),
    },
    { key: 'score', header: '점검 필요도', width: 112, sortable: true, align: 'right', render: (r) => <span className="num">{r.score}점</span> },
    {
      key: 'obstacle',
      header: '주요 보행 방해요소',
      width: 176,
      sortable: true,
      render: (r) => (r.obstacleRest > 0 ? `${r.obstacleMain} 외 ${r.obstacleRest}건` : r.obstacleMain),
    },
    {
      key: 'reliability',
      header: '자료 신뢰도',
      width: 96,
      sortable: true,
      align: 'center',
      render: (r) => (
        <span className={styles.reli}>
          <Badge tone={RELI_TONE[r.reliability]}>{r.reliability}</Badge>
          {r.reliability === '낮음' ? (
            <Tag tone="mid" small>
              {LIST.needCheck}
            </Tag>
          ) : null}
        </span>
      ),
    },
    { key: 'unrated', header: '평가하지 못한 분야 수', width: 172, sortable: true, align: 'right', render: (r) => <span className="num">{r.unratedCount}</span> },
    {
      key: 'decision',
      header: '결정 상태',
      width: 128,
      stickyRight: true, // 가로 스크롤돼도 결정 상태 칸은 늘 보인다
      sortable: true,
      align: 'center',
      // 도로관리팀 · 검토 중 · 구 확정 전에만 메뉴 버튼이다. 그 밖에는 글자만 보인다 (정의서 US-01 1-4, CM-00 10번).
      render: (r) => (canDecide && r.gu ? <DecisionMenu value={r.decision} label={LIST.decisionMenuLabel} onSelect={(d) => onDecide(r, d)} /> : r.decision),
    },
  );
  return cols;
}

/** 2-3 순위 표. 한 쪽 50행. 행을 누르면 요약 팝업이 열리고 지도가 그 구역으로 옮겨 간다. */
export default function RankTable({ rows, city, canDecide, conditionMap, onDecide, selectedId, onSelect, sort, onSort, emptyContent }) {
  return (
    <DataTable
      caption={LIST.tableCaption}
      columns={columnsFor({ city, canDecide, conditionMap, onDecide })}
      rows={rows}
      getRowKey={(r) => r.gid}
      selectedKey={selectedId}
      onRowClick={(r) => onSelect(r.gid)}
      rowLabel={(r) => `${r.rank}위 ${placeLabel(r)}`}
      sort={sort}
      onSort={onSort}
      rowTone={(r) => (r.tier === 'top' ? 'high' : null)}
      fixed
      emptyContent={emptyContent}
    />
  );
}
