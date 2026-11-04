// 기준정보·알림·분류 검수 가짜 데이터 (US-00 알림, US-10~US-14)
import { OBSTACLES } from './generate.js';
import { ROLE } from '../shared/constants.js';

/** US-12 데이터 목록. 자료 이름과 제공기관은 DB v1.9 56_source_list를 따랐고, 기준일·최신 여부는 가짜다. */
export const DATA_LIST = [
  { id: 'd1', name: '보행자 교통사고 다발지역', org: '도로교통공단', basis: '2025년 기준', updateType: '연간', freshness: '최신', share: '공유 가능 (출처 표시)' },
  { id: 'd2', name: '국토지리정보원 수치지형도 1:5,000', org: '국토지리정보원', basis: '2025년 기준', updateType: '연간', freshness: '최신', share: '공유 가능 (출처 표시)' },
  { id: 'd3', name: '전국횡단보도표준데이터 (성남)', org: '성남시', basis: '2025년 기준', updateType: '연간', freshness: '최신', share: '공유 가능' },
  { id: 'd4', name: '보안등정보', org: '성남시', basis: '2025년 기준', updateType: '연간', freshness: '최신', share: '공유 가능' },
  { id: 'd5', name: '성남시 도로 조도·휘도', org: '성남시', basis: '2022년 기준', updateType: '1회성', freshness: '최신', share: '공유 가능' },
  { id: 'd6', name: '주정차 위반 단속 위치 현황', org: '성남시', basis: '2026.06 기준', updateType: '반기', freshness: '갱신 예정일 지남', share: '공유 가능' },
  { id: 'd7', name: '성남데이터넷 연도별 민원 현황', org: '성남시', basis: '2026.06 기준', updateType: '반기', freshness: '최신', share: '공유 가능 (출처 표시, 공공누리 제1유형)' },
  { id: 'd8', name: '경찰서 보행신호 (중원·분당·수정)', org: '성남중원·분당·성남수정경찰서', basis: '2026.03 기준', updateType: '1회성', freshness: '최신', share: '미확인' },
  { id: 'd9', name: '유동인구 (KT 추정, 행정동)', org: '경기도', basis: '2025.12 기준', updateType: '반기', freshness: '갱신 예정일 지남', share: '미확인' },
  { id: 'd10', name: '어린이집·유치원', org: '교육부 유치원알리미', basis: '2025년 기준', updateType: '연간', freshness: '최신', share: '공유 가능 (출처 표시)' },
  { id: 'd11', name: '노인의료복지시설', org: '경기도', basis: '2025년 기준', updateType: '연간', freshness: '최신', share: '공유 가능' },
  { id: 'd12', name: '차로별 도로현황', org: '성남시', basis: '기준일 미확인', updateType: null, freshness: '빠짐', share: '미확인' },
];

/** US-13 규정 변경 (날짜 순) */
export const REGULATIONS = [
  { id: 'g1', name: '보도 설치 및 관리 지침', changed: '3.2 유효 보도 폭', date: '2026.09.01' },
  { id: 'g2', name: '성남시 사무위임 조례', changed: '별표 1 도로유지관리', date: '2026.05.20' },
  { id: 'g3', name: '수정구 업무분장', changed: '건설과 도로관리팀', date: '2026.03.04' },
];

/** US-10 승인 대기 제안 (오래된 순) */
export const PROPOSALS = [
  {
    id: 'p1',
    kind: '산정 기준',
    version: 'v1.3',
    summary: '반영 비율 조정',
    date: '2026.11.03',
    changes: [{ type: 'weight', field: '보도', from: '20%', to: '25%' }],
    impact: { top: 50, changed: 4 },
  },
];

/** US-11 분류 검수 표본 (구 도로관리팀, 자기 구 민원만) */
const SAMPLE_BASE = [
  ['…역 출구 앞 인도에 차가 올라와…', '주정차', '인도, 차'],
  ['…횡단보도 앞에 차량이 계속 서 있어…', '주정차', '횡단보도, 차량'],
  ['…학교 앞 인도가 좁아 걷기 어려워…', '보행로', '인도, 좁아'],
  ['…건널목 신호가 너무 빨리 바뀌어…', '신호', '신호, 바뀌어'],
  ['…골목 가로등이 꺼져 밤에 어두워…', '조명', '가로등, 어두워'],
  ['…상가 앞 인도에 물건을 쌓아 두어…', '점유', '인도, 물건'],
  ['…큰 도로를 건널 때 중간에 쉴 곳이 없어…', '시설', '건널, 중간'],
  ['…버스정류장 횡단보도에 상습 주차…', '주정차', '횡단보도, 주차'],
  ['…동 주민센터에 문의했는데 답이 없어…', null, '문의, 답변', '불명'], // 관련 여부가 불명이면 유형은 비운다
];
export const CLASSIFY_SAMPLES = Object.fromEntries(
  ['수정구', '중원구', '분당구'].map((gu, gi) => [
    gu,
    SAMPLE_BASE.map((row, i) => ({
      id: `cl-${gi}-${i}`,
      gu,
      summary: row[0],
      label: row[1],
      keywords: row[2],
      relevance: row[3] || '관련',
    })),
  ]),
);

/** US-14 조치 제안 표 (대장 05_03 조치 제안 표를 따른다. 보기만 한다) */
export const ACTION_TABLE = OBSTACLES.filter((o, i, arr) => arr.findIndex((x) => x.problem === o.problem) === i).map(
  (o) => ({
    id: o.key,
    problem: o.problem,
    check: o.check,
    action: o.action,
    sentence: o.sentence,
    dept: o.tableDept,
    article: o.article,
  }),
);

/** US-00 알림. role: 누가 받는지, kind: 눌렀을 때 가는 곳 */
export const NOTIFICATIONS = [
  { id: 'n1', roles: [ROLE.CITY], kind: 'approval', date: '2026.11.03', text: (c) => `산정 기준 ${c.version} 승인 요청이 왔습니다.` },
  { id: 'n2', roles: [ROLE.CITY], kind: 'runOpen', date: '2026.11.01', text: (c) => `${c.runTitle}가 열렸습니다. 3개 구 점검 후보를 확인해 보세요.` },
  { id: 'n3', roles: [ROLE.DISTRICT], kind: 'runOpen', date: '2026.11.01', text: (c) => `${c.runTitle}가 열렸습니다. ${c.gu} 점검 후보를 결정해 주세요.` },
  { id: 'n4', roles: [ROLE.CITY, ROLE.DISTRICT], kind: 'halfYear', date: '2026.07.15', text: (c) => `${c.refTitle}이 열렸습니다. 바뀐 순위를 확인해 보세요.` },
];
