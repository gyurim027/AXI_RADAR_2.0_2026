// 어드민 가짜 자료(씨앗 값). 기능정의서 10_3_화면명세_어드민의 예시 문구를 바탕으로 한 가안이다.
// 이 파일에는 바뀌지 않는 처음 값만 둔다. 화면에서 바꾼 값은 store.js 상태에 남는다.
import { DATA_LIST } from './reference.js';

/** 가짜 서버가 "지금"으로 보는 날. 최근 30일 같은 기간 계산이 늘 같은 결과를 내도록 고정한다. */
export const MOCK_NOW = '2026-11-20T15:00:00';
export const OPERATOR_NAME = '이시범';
export const OPERATOR_LABEL = `${OPERATOR_NAME} (RADAR 운영팀)`;

export const RECEIVED_FROM = ['공공데이터포털 API', '파일', '시 내부 자료'];
export const FRESHNESS = ['최신', '갱신 예정일 지남', '빠짐'];
export const OFFICIAL = ['공식 원본', '가공본', '미확인'];
export const UPLOAD_FORMATS = ['CSV', 'XLSX', 'SHP', 'DXF'];

// ------------------------------------------------------------------ 데이터 (AD-02)
/** 받은 곳, 외부 AI 전송, 공식 원본 여부는 가안이다. 이름과 제공기관은 사용자 화면 데이터 목록과 같다. */
const EXTRA = {
  d1: { source: '공공데이터포털 API', official: '공식 원본', ai: '가능', collectedAt: '2026.03.10' },
  d2: { source: '파일', official: '공식 원본', ai: '불가', collectedAt: '2026.02.04' },
  d3: { source: '공공데이터포털 API', official: '공식 원본', ai: '가능', collectedAt: '2026.03.10' },
  d4: { source: '공공데이터포털 API', official: '공식 원본', ai: '가능', collectedAt: '2026.03.10' },
  d5: { source: '시 내부 자료', official: '가공본', ai: '불가', collectedAt: '2025.12.02' },
  d6: { source: '파일', official: '가공본', ai: '가능', collectedAt: '2026.07.15' },
  d7: { source: '파일', official: '공식 원본', ai: '가능', collectedAt: '2026.07.15' },
  d8: { source: '시 내부 자료', official: '미확인', ai: '불가', collectedAt: '2026.03.28' },
  d9: { source: '공공데이터포털 API', official: '공식 원본', ai: '가능', collectedAt: '2026.01.12' },
  d10: { source: '공공데이터포털 API', official: '공식 원본', ai: '가능', collectedAt: '2026.03.10' },
  d11: { source: '공공데이터포털 API', official: '공식 원본', ai: '가능', collectedAt: '2025.10.30' },
  d12: { source: '시 내부 자료', official: '미확인', ai: '불가', collectedAt: null },
};
const ORDER = ['d2', 'd1', 'd3', 'd4', 'd5', 'd6', 'd7', 'd8', 'd9', 'd10', 'd11', 'd12'];

export const DATA_ITEMS = [
  ...ORDER.map((key, i) => {
    const base = DATA_LIST.find((d) => d.id === key);
    const ex = EXTRA[key];
    const stale = key === 'd11'; // 세 번째 '갱신 예정일 지남' 자료 (대시보드 예시: 기준일 지난 자료 3종)
    return {
      id: `DAT-${String(i + 1).padStart(2, '0')}`,
      userKey: key,
      name: base.name,
      org: base.org,
      source: ex.source,
      cycle: base.updateType, // 연간 / 반기 / 1회성 / null
      basis: base.basis === '기준일 미확인' ? null : base.basis,
      collectedAt: ex.collectedAt,
      official: ex.official,
      freshness: stale ? '갱신 예정일 지남' : base.freshness,
      share: base.share,
      ai: ex.ai,
      uploaded: ex.source !== '공공데이터포털 API',
    };
  }),
  {
    id: 'DAT-13',
    userKey: 'd13',
    name: '보도 폭 측정 자료 (시 내부)',
    org: '성남시 도로과',
    source: '시 내부 자료',
    cycle: '연간',
    basis: null,
    collectedAt: null,
    official: '가공본',
    freshness: '빠짐',
    share: '미확인',
    ai: '불가',
    uploaded: true,
  },
];

/** 회차별 원본 목록(파일로 올린 자료). 올린 날, 올린 운영자 */
export const SEED_FILES = {
  'DAT-02': [{ run: '2027 연간', at: '2026-10-11', by: OPERATOR_LABEL, file: 'dongmin_walk_accident_2025.csv' }],
  'DAT-06': [{ run: '2026 하반기 참고', at: '2026-07-15', by: OPERATOR_LABEL, file: 'parking_enforcement_2026h1.csv' }],
  'DAT-07': [{ run: '2026 하반기 참고', at: '2026-07-15', by: OPERATOR_LABEL, file: 'complaint_2021_2026h1.csv' }],
  'DAT-05': [{ run: '2026 연간', at: '2025-12-02', by: OPERATOR_LABEL, file: 'light_survey_2022.xlsx' }],
  'DAT-08': [{ run: '2026 연간', at: '2026-03-28', by: OPERATOR_LABEL, file: 'police_signal.xlsx' }],
};

// ------------------------------------------------------------------ 올린 기록, 검사 결과 (AD-03, AD-04)
export const SEED_UPLOADS = [
  {
    id: 'up-3',
    at: '2026-10-18T10:20:00',
    by: OPERATOR_LABEL,
    dataId: 'DAT-13',
    dataName: '보도 폭 측정 자료 (시 내부)',
    basis: '2026년 기준',
    source: '성남시 도로과 제공',
    file: 'sidewalk_width_2026.csv',
    errors: 3,
  },
  {
    id: 'up-2',
    at: '2026-10-11T09:40:00',
    by: OPERATOR_LABEL,
    dataId: 'DAT-02',
    dataName: '보행자 교통사고 다발지역',
    basis: '2025년 기준',
    source: '도로교통공단',
    file: 'dongmin_walk_accident_2025.csv',
    errors: 0,
  },
  {
    id: 'up-1',
    at: '2026-07-15T16:05:00',
    by: OPERATOR_LABEL,
    dataId: 'DAT-06',
    dataName: '주정차 위반 단속 위치 현황',
    basis: '2026.06 기준',
    source: '성남시',
    file: 'parking_enforcement_2026h1.csv',
    errors: 2,
  },
];

/** 탭 4개. fixedBy: 이 데이터를 오류 없이 다시 올리면 사라지는 행 */
export const SEED_CHECKS = {
  format: [
    { id: 'c1', dataId: 'DAT-13', data: '보도 폭 측정 자료 (시 내부)', row: 128, kind: '필수 칸 비어 있음', reason: '기준일 칸이 비었음' },
    { id: 'c2', dataId: 'DAT-13', data: '보도 폭 측정 자료 (시 내부)', row: 131, kind: '필수 칸 비어 있음', reason: '보도 면적 칸이 비었음' },
    { id: 'c3', dataId: 'DAT-13', data: '보도 폭 측정 자료 (시 내부)', row: 240, kind: '형식이 다름', reason: '숫자 칸에 글자가 들어 있음' },
  ],
  value: [
    { id: 'c4', dataId: 'DAT-06', data: '주정차 위반 단속 위치 현황', row: 412, kind: '성남시 밖 좌표', reason: '경도 126.4가 성남시 범위를 벗어남' },
    { id: 'c5', dataId: 'DAT-06', data: '주정차 위반 단속 위치 현황', row: 1033, kind: '지난 회차보다 크게 바뀐 값', reason: '단속 건수가 지난 회차보다 9배 많음' },
  ],
  location: [
    { id: 'c6', dataId: 'DAT-07', data: '성남데이터넷 연도별 민원 현황', row: 20871, kind: '좌표를 못 붙임', reason: '주소가 "○○로 일대"로만 적혀 있음' },
    { id: 'c7', dataId: 'DAT-07', data: '성남데이터넷 연도별 민원 현황', row: 20902, kind: '도로 단위', reason: '도로 이름만 있고 번지가 없음' },
    { id: 'c8', dataId: 'DAT-07', data: '성남데이터넷 연도별 민원 현황', row: 21144, kind: '좌표를 못 붙임', reason: '주소가 비어 있음' },
  ],
  group: [
    { id: 'c9', dataId: 'DAT-03', data: '전국횡단보도표준데이터 (성남)', row: 3310, kind: '같은 시설 묶기에서 남음', reason: '30m 안에 묶을 시설이 없음' },
    { id: 'c10', dataId: 'DAT-04', data: '보안등정보', row: 877, kind: '같은 시설 묶기에서 남음', reason: '30m 안에 묶을 시설이 없음' },
  ],
};
/** 위치 낮음 민원 (AD-04 1-2). 숫자를 누르면 목록을 연다. */
export const LOW_LOCATION = { count: 354, topCells: 50, changedCells: 0 };

// ------------------------------------------------------------------ 분류 검수 (AD-05)
export const RELEVANCE = ['관련', '비관련', '불명'];

// ------------------------------------------------------------------ 실행 기록 (AD-07)
const at = (d, t) => `2026-${d}T${t}:00`;
const done = (n, name, kind, runName, d, t, minutes, status = '성공', note = null) => ({
  id: `ex-${n}`,
  name,
  kind,
  status,
  at: at(d, t),
  minutes,
  runName,
  logs: [`[${t}] ${kind}을 시작했습니다.`, ...(note ? [`[${t}] ${note}`] : []), `[${t}] 끝났습니다. 걸린 시간 ${minutes}분`],
});
/** 최근 30일 15건: 성공 12 · 실패 1 · 경고 2 (대시보드 예시와 같다) */
export const SEED_EXECUTIONS = [
  {
    id: 'ex-15',
    name: '2028 연간 산정',
    kind: '산정',
    status: '실패',
    at: at('11-18', '14:02'),
    minutes: 18,
    runName: '2028 연간',
    cause: '보도 면적 열이 비어 있음',
    logs: [
      '[14:02] 산정을 시작했습니다.',
      '[14:11] 보도 폭 측정 자료를 읽었습니다.',
      '[14:20] 지표 계산 실패: 보도 면적 열이 비어 있음 (격자 3,412개)',
    ],
  },
  done(14, '2027 연간 산정', '산정', '2027 연간', '11-12', '10:00', 21, '경고', '경고: 연결성 자료가 없어 평가하지 못한 분야로 두었습니다.'),
  done(13, '공공데이터 주간 점검', '수집', '-', '11-08', '03:00', 6, '경고', '경고: 유동인구 자료의 갱신 예정일이 지났습니다.'),
  done(12, '2027 연간 산정', '산정', '2027 연간', '11-10', '09:30', 20),
  ...['11-15', '11-13', '11-11', '11-09', '11-07', '11-05', '11-03', '11-01', '10-29', '10-26', '10-23'].map((d, i) =>
    done(11 - i, '공공데이터 수집', '수집', '-', d, '03:00', 5 + (i % 3)),
  ),
];

// ------------------------------------------------------------------ 실행 일정 (AD-08)
export const SCHEDULE = [
  { id: 's1', name: '공공데이터 반기 수집', cycle: '반기', next: '2027.01.15', last: '2026.07.15' },
  { id: 's2', name: '민원 파일 반기 정제', cycle: '반기', next: '2027.01.20', last: '2026.07.20' },
  { id: 's3', name: '연간 산정', cycle: '연 1회', next: '2027.10.01', last: '2026.10.01' },
];

// ------------------------------------------------------------------ 산정 기준 (AD-09, AD-10)
export const INDICATORS = [
  { id: 'w1', field: '보도', name: '도로 1km당 보도 면적', weight: 20 },
  { id: 'w2', field: '보도', name: '보도 폭 2.0m 미만 비율', weight: 10 },
  { id: 'w3', field: '횡단보도', name: '보행 신호시간 확인 불가', weight: 8 },
  { id: 'w4', field: '횡단보도', name: '중간 대피 공간 없음', weight: 8 },
  { id: 'w5', field: '조도', name: '야간 평균 조도', weight: 8 },
  { id: 'w6', field: '사고', name: '보행자 사고 다발 지점 근접', weight: 14 },
  { id: 'w7', field: '민원', name: '보행 관련 민원 건수', weight: 8 },
  { id: 'w8', field: '민원', name: '민원 재발', weight: 6 },
  { id: 'w9', field: '주정차', name: '인도 불법 주정차 민원', weight: 4 },
  { id: 'w10', field: '주정차', name: '횡단보도 불법 주정차 민원', weight: 4 },
  { id: 'w11', field: '보호구역', name: '어린이 보호구역 근접', weight: 6 },
  { id: 'w12', field: '보호구역', name: '고령자 시설 근접', weight: 4 },
];
export const THRESHOLDS = [
  { id: 't1', name: '같은 시설 묶기 거리', value: 30, unit: 'm' },
  { id: 't2', name: '보호구역 근접 거리', value: 300, unit: 'm' },
  { id: 't3', name: '평가 제외 결측 지표 수', value: 3, unit: '개' },
  { id: 't4', name: '사고 다발지 반복 기준', value: 3, unit: '년' },
  { id: 't5', name: '민원 재발 기준', value: 2, unit: '건' },
];
export const CONDITIONS = [
  { id: 'k1', name: '사고 다발지 반복 선정', value: '3년 이상', ratio: 40, use: true },
  { id: 'k2', name: '민원 재발', value: '2건 이상', ratio: 20, use: true },
];

/** 버전 목록의 처음 상태. 값은 weights/thresholds/conditions로 따로 두고, 바뀐 값만 versionEdits에 남긴다. */
export const SEED_VERSIONS = [
  { version: 'v1.1', name: '첫 해 기준', run: '2026 연간', status: '승인됨', updated: '2025.11.20', base: null },
  { version: 'v1.2', name: '민원 반영 기준', run: '2027 연간', status: '승인됨', updated: '2026.08.30', base: 'v1.1' },
  { version: 'v1.3', name: '보도 가중치 조정', run: '2028 연간', status: '승인 대기', updated: '2026.11.03', base: 'v1.2' },
];
/** 버전별로 이전 버전과 다른 값 (없으면 base 값을 그대로 쓴다) */
export const VERSION_VALUES = {
  'v1.1': { weights: { w1: 22, w2: 10, w5: 8, w6: 16, w7: 6, w8: 4, w9: 4, w10: 4, w11: 6, w12: 4 }, thresholds: { t1: 30, t2: 300, t3: 3, t4: 3, t5: 2 }, conditions: [{ id: 'k1', name: '사고 다발지 반복 선정', value: '3년 이상', ratio: 40, use: true }] },
  'v1.2': { weights: {}, thresholds: {}, conditions: CONDITIONS },
  'v1.3': { weights: { w1: 25, w6: 9 }, thresholds: {}, conditions: CONDITIONS },
};

// ------------------------------------------------------------------ 담당 부서 표 (AD-11)
export const JURISDICTION = [
  { id: 'JUR-01', problem: '보도 폭 부족', dept: '각 구 건설과 도로관리팀', related: '시 도로과', status: '확인됨', basis: '사무위임 조례 별표1' },
  { id: 'JUR-02', problem: '보도 파손·단차·점자블록', dept: '수정구 건설과 도로관리팀', related: '시 도로과', status: '확인됨', basis: '사무위임 조례 별표1' },
  { id: 'JUR-03', problem: '횡단보도 신호시간', dept: '시 교통기획과 교통시설팀', related: '관할 경찰서', status: '확인됨', basis: '도로교통법 제6조' },
  { id: 'JUR-04', problem: '조도 부족', dept: '각 구 건설과 도로조명팀', related: '시 도로과', status: '확인됨', basis: '사무위임 조례 별표1' },
  { id: 'JUR-05', problem: '불법 주정차', dept: '각 구 경제교통과 주차관리팀', related: '관할 경찰서', status: '확인됨', basis: '도로교통법 제32조' },
  { id: 'JUR-06', problem: '중간 대피 공간 없음', dept: '-', related: '시 교통기획과 교통시설팀', status: '확인 필요', basis: '근거 없음' },
  { id: 'JUR-07', problem: '불법 적치', dept: '시 도로과 도로행정팀', related: '각 구 건설과', status: '확인됨', basis: '사무위임 규칙 별표1' },
];
export const DEPT_DRAFTS = [
  {
    id: 'dd1',
    problem: '불법 적치',
    from: '시 도로과 도로행정팀',
    to: '수정구 건설과 도로관리팀',
    basis: '사무위임 규칙 별표1',
    article: '사무위임 규칙 별표1 (도로 점용·적치물 관리 사무: 구청장에게 위임)',
    jurId: 'JUR-07',
  },
];

// ------------------------------------------------------------------ 규정 변경 (AD-12)
export const ADMIN_REGULATIONS = [
  {
    id: 'g1',
    kind: '법령',
    name: '보도 설치 및 관리 지침',
    where: '3.2 유효 보도 폭',
    date: '2026.09.01',
    juris: ['JUR-02', 'JUR-03'],
    before: '유효 보도 폭은 2.0m 이상으로 한다.',
    after: '유효 보도 폭은 2.0m 이상으로 하되, 보행량이 많은 곳은 2.5m 이상으로 한다.',
    pending: false,
  },
  {
    id: 'g2',
    kind: '법령',
    name: '성남시 사무위임 조례',
    where: '별표 1 도로유지관리',
    date: '2026.05.20',
    juris: ['JUR-01', 'JUR-07'],
    before: '도로 점용·적치물 관리: 시장',
    after: '도로 점용·적치물 관리: 구청장',
    pending: false,
  },
  {
    id: 'g3',
    kind: '업무분장',
    name: '수정구 업무분장',
    where: '건설과 도로관리팀',
    date: '2026.03.04',
    juris: ['JUR-02'],
    before: '도로관리팀: 도로 유지보수',
    after: '도로관리팀: 도로 유지보수, 적치물 정비',
    pending: false,
  },
  {
    id: 'g4',
    kind: '법령',
    name: '도로교통법 시행규칙',
    where: '보행 신호 기준 조항',
    date: '2026.11.10',
    juris: ['JUR-03'],
    before: '보행 신호 시간은 보행 속도 1.0m/초를 기준으로 한다.',
    after: '보행 신호 시간은 보행 속도 0.8m/초를 기준으로 한다.',
    pending: true, // 시행 전 판
  },
];

// ------------------------------------------------------------------ 승인 이력 (AD-14)
export const SEED_APPROVALS = [
  { id: 'ap-1', target: '산정 기준', version: 'v1.2', proposer: OPERATOR_LABEL, at: '2026-08-28', approver: '박사례 (성남시 도로과 도로관리팀)', result: '승인', reason: '-', ref: { kind: 'criteria', version: 'v1.2' } },
  { id: 'ap-2', target: '담당 부서 표', version: '-', proposer: OPERATOR_LABEL, at: '2026-06-20', approver: '박사례 (성남시 도로과 도로관리팀)', result: '돌려받음', reason: '근거 조문 확인 필요', ref: { kind: 'dept', draftId: 'dd0' } },
  { id: 'ap-3', target: '산정 기준', version: 'v1.1', proposer: OPERATOR_LABEL, at: '2025-11-18', approver: '박사례 (성남시 도로과 도로관리팀)', result: '승인', reason: '-', ref: { kind: 'criteria', version: 'v1.1' } },
];

// ------------------------------------------------------------------ 조치 제안 표 검토 상태 (AD-13)
export const REVIEW_STATES = ['초안', '검토 완료', '사용 중지'];

// ------------------------------------------------------------------ 계정 (AD-15)
export const ROLE_OPTIONS = ['시 도로과', '구 도로관리팀', 'RADAR 운영자'];
export const SEED_PEOPLE = {
  suj: { name: '김수정', team: '도로관리팀', last: '2026.11.20' },
  jungwon: { name: '이중원', team: '도로관리팀', last: '2026.11.19' },
  bundang: { name: '박분당', team: '도로관리팀', last: '2026.11.20' },
  'bundang-sidewalk': { name: '최보도', team: '보도관리팀', last: '2026.11.18' },
  city: { name: '박사례', team: '도로관리팀', last: '2026.11.20' },
  operator: { name: OPERATOR_NAME, team: 'RADAR 운영팀', last: '2026.11.20' },
};
export const SEED_ROLE_LOG = [
  { id: 'rl-1', at: '2026-11-01', name: '최보도', from: '-', to: '구 도로관리팀', by: OPERATOR_LABEL },
  { id: 'rl-2', at: '2026-10-05', name: '박사례', from: '-', to: '시 도로과', by: OPERATOR_LABEL },
];

// ------------------------------------------------------------------ 접속 기록 (AD-16)
export const ACCESS_ACTIONS = ['로그인', '화면 열람', '파일 내려받기', '결정', '승인', '설정 변경', '사용자 화면 보기'];
export const SEED_ACCESS = [
  { at: '2026-11-20T10:14:00', actor: OPERATOR_LABEL, accountId: 'operator', ip: '10.12.3.45', action: '파일 내려받기', target: '2027 수정구 관할 부서별 보고서', reason: '-' },
  { at: '2026-11-19T17:02:00', actor: '수정구 건설과 도로관리팀', accountId: 'suj', ip: '10.12.8.21', action: '결정', target: '수정구 점검 후보 결정 12건', reason: '-' },
  { at: '2026-11-19T09:11:00', actor: '성남시 도로과 도로관리팀', accountId: 'city', ip: '10.12.1.9', action: '로그인', target: '-', reason: '-' },
  { at: '2026-11-12T11:40:00', actor: '성남시 도로과 도로관리팀', accountId: 'city', ip: '10.12.1.9', action: '화면 열람', target: '구별 우선 점검 근거표', reason: '-' },
  { at: '2026-11-03T15:20:00', actor: OPERATOR_LABEL, accountId: 'operator', ip: '10.12.3.45', action: '설정 변경', target: '산정 기준 v1.3 승인 요청', reason: '-' },
  { at: '2026-10-28T13:05:00', actor: '분당구 건설과 보도관리팀', accountId: 'bundang-sidewalk', ip: '10.12.9.14', action: '로그인', target: '-', reason: '-' },
];

/** 갱신 예정일이 지난 자료의 예정일 (알림 날짜) */
export const STALE_DUE = { 'DAT-06': '2026.11.15', 'DAT-09': '2026.07.01', 'DAT-11': '2026.10.30' };

// ------------------------------------------------------------------ 조치 제안 문장 틀 초안 (AD-13 1-2)
export const ACTION_DRAFTS = [
  {
    id: 'ad1',
    actionId: 'sidewalk',
    sentence:
      '도면에서 잰 보도 폭이 2.0m보다 좁습니다. 실제로 걸을 수 있는 폭을 현장에서 재 주세요. 보행량이 많은 곳은 2.5m 기준도 같이 확인해 주세요.',
    article: '보도 설치 및 관리 지침 3.2',
    articleText:
      '3.2 유효 보도 폭: 유효 보도 폭은 2.0m 이상으로 하되, 보행량이 많은 곳은 2.5m 이상으로 한다. (2026.09.01 개정)',
  },
];

/** 근거 원문 (옆 패널). 가안 문구이며 실제 조문과 다를 수 있다. */
export const ARTICLE_TEXTS = {
  'JUR-07': '사무위임 규칙 별표1: 도로 점용·적치물 관리 사무는 구청장에게 위임한다. (2026.05.20 개정)',
};
