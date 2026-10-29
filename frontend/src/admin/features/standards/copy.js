// 기준정보 묶음 문구 (10_3_화면명세_어드민 AD-09~AD-14). 기능정의서 문구가 바뀌면 이 파일만 고친다.

export const CRITERIA = {
  // AD-09
  title: '산정 기준',
  subtitle: '가중치·기준값·우선 확인 조건의 버전을 관리합니다. 시 도로과가 승인한 버전만 산정에 사용할 수 있습니다.',
  statusLabel: '상태',
  statuses: ['전체', '작성 중', '승인 대기', '승인됨', '반려'],
  create: '새 버전 만들기',
  head: ['버전', '버전 이름', '적용 회차', '상태', '수정일', '사용 지표 수'],
  empty: "아직 만든 산정 기준이 없습니다. '새 버전 만들기'로 시작해 주세요.", // E-5
  caption: '산정 기준 버전 목록',
  failedArea: '산정 기준 버전 목록',
  createFailed: '새 버전을 만들지 못했습니다.',
};

export const DETAIL = {
  // AD-10
  title: (version) => `산정 기준 ${version}`,
  run: (name) => `적용 회차: ${name}`,
  subtitle: '값을 고치고 이유를 적어 시 도로과에 승인을 요청합니다. 승인되면 다음 산정부터 사용할 수 있습니다.',
  returned: (reason) => `반려 사유: ${reason}`,
  tabs: { weights: '가중치', thresholds: '기준값', conditions: '우선 확인 조건' },
  back: '버전 목록으로 돌아가기',
  failedArea: '산정 기준',

  weightsHead: ['분야', '지표', '현재 가중치', '이전 가중치'],
  weightsSum: (n) => `가중치 합계 ${n}%`,
  thresholdsHead: ['기준값', '현재 값', '이전 값', '단위'],
  conditionsHead: ['조건', '기준값', '반영 비율', '사용'],
  addCondition: '조건 추가하기',
  conditionName: '조건 이름',
  use: '사용',
  useOff: '사용 안 함',

  usedTitle: '이 버전이 쓰는 지표',
  usedHead: ['분야', '지표', '자료', '값 상태'],
  toApprovals: '승인 이력에서 보기',

  previewTitle: '상위 후보 변화 미리 보기',
  previewBody: (top, changed) => `상위 ${top}곳 중 ${changed}곳이 바뀝니다.`,
  recalc: '변화 다시 계산하기',
  recalcedAt: (t) => `마지막 계산 ${t}`,

  reasonLabel: '변경 사유',
  reasonPlaceholder: '예: 시 도로과 검토 의견 반영',
  reasonError: '변경 사유를 적어 주세요.',
  request: '승인 요청하기',
  requested: '승인을 요청했습니다. 시 도로과가 승인하면 다음 산정부터 사용할 수 있습니다.',
};

export const DEPT = {
  // AD-11
  title: '담당 부서 표',
  subtitle: '문제 유형별 1차 해결 부서를 관리합니다. 수정안은 시 도로과가 승인해야 사용할 수 있습니다.',
  currentTitle: '현재 표',
  currentHead: ['관할 ID', '문제 유형', '1차 해결 부서', '유관 부서', '확인 상태', '근거'],
  currentCaption: '현재 담당 부서 표',
  draftTitle: '수정안 (AI가 만든 초안)',
  draftsNotConnected: '수정안은 아직 서버에서 받을 수 없습니다. 수정안을 서버에 올리는 기능은 있지만, 올린 수정안을 불러오는 기능이 아직 없습니다.', // 제안 문구: 정의서 AD-11에 없음
  draftRow: (problem, from, to) => `${problem} · ${from} → ${to}`,
  draftBasis: (basis) => `근거 조문: ${basis}`,
  viewArticle: '근거 원문 보기',
  articleClose: '근거 원문 닫기',
  reasonLabel: '제안 이유',
  request: '수정안 승인 요청하기',
  note: '승인 전에는 현재 표를 그대로 사용합니다.',
  empty: '새 수정안이 없습니다.',
  // 명세에 요청 뒤 문구가 없어 산정 기준(AD-10 5-1)의 완료 문구를 그대로 쓴다
  requested: '승인을 요청했습니다. 시 도로과가 승인하면 다음 산정부터 사용할 수 있습니다.',
  failedArea: '담당 부서 표',
};

export const REGS = {
  // AD-12
  title: '규정 변경',
  subtitle: '근거로 쓰는 법령과 업무분장이 바뀐 내역을 확인합니다.',
  head: ['종류', '규정 제목', '변경 대상', '시행일', '영향받는 관할'],
  caption: '규정 변경 목록',
  beforeTitle: '변경 전',
  afterTitle: '변경 후',
  detected: (date) => `변경 감지일 ${date}`, // RADAR가 변경을 찾은 날
  jurCount: (n) => `관할 ${n}곳`,
  jurHead: ['관할', '조건', '담당 부서'],
  toDeptRow: '담당 부서 표에서 보기',
  pending: '시행 전',
  toDept: '담당 부서 표로 가기',
  empty: '바뀐 법령이나 업무분장이 없습니다.',
  failedArea: '규정 변경',
};

export const ACTIONS = {
  // AD-13
  title: '조치 제안 표',
  subtitle: '데이터로 찾은 문제마다 현장에서 확인할 것, 요청할 조치, 받는 부서를 정리한 표를 관리합니다.',
  head: ['항목 ID', '데이터로 찾은 문제', '확인할 것', '조치', '조치 제안 문장', '받는 부서', '근거 조문', '검토 상태'],
  caption: '조치 제안 표',
  download: '현재 조치 제안 표 내려받기',
  editRow: '문장 틀 고치기',
  note: '검토 완료인 행만 사용자 화면에 보입니다.',
  saved: (ck) => `${ck} 행을 저장했습니다. 다음 조치 제안부터 사용합니다.`,
  deptNone: '받는 부서 확인 필요',
  articleNone: '근거 조문 확인 중',
  reviewStates: ['초안', '검토 완료', '사용 중지'],
  failedArea: '조치 제안 표',

  editTitle: (ck) => `${ck} 문장 틀 고치기`,
  editClose: '문장 틀 고치기 창 닫기',
  fCheck: '확인할 것',
  fAction: '조치',
  fSentence: '조치 제안 문장',
  fDept: '받는 부서',
  fArticle: '근거 조문',
  fReview: '검토 상태',
  editSave: '고친 행 저장하기',

  draftTitle: '문장 틀 초안 (AI가 만든 초안)',
  draftArticle: (a) => `근거 조문: ${a}`,
  viewArticle: '근거 원문 보기',
  articleClose: '근거 원문 닫기',
  draftSave: '문장 틀 저장하기',
  draftNote: '저장하기 전에는 현재 문장 틀을 그대로 사용합니다.',
  draftEmpty: '새 문장 틀 초안이 없습니다.',
};

export const APPROVALS = {
  // AD-14
  title: '승인 이력',
  subtitle: '누가 언제 무엇을 왜 바꿨는지 봅니다.',
  period: '기간',
  // 해는 올해·작년 대신 숫자로 쓴다 (K-23)
  periods: (year) => [`${year}년`, `${year - 1}년`, '전체'],
  head: ['대상', '버전', '제안자', '제안일', '승인자', '결과', '사유'],
  caption: '승인 이력',
  fix: '반려된 제안 고치기',
  chip: (result) => `결과: ${result}`,
  chipRemove: (result) => `결과 ${result} 필터 지우기`,
  empty: '조건에 맞는 이력이 없습니다.',
  emptyClear: '필터 모두 지우기',
  failedArea: '승인 이력',
};
