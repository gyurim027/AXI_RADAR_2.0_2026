// 데이터 묶음 문구 (10_3_화면명세_어드민 AD-02~AD-05). 기능정의서 문구가 바뀌면 이 파일만 고친다.

export const LIST = {
  // AD-02
  title: '데이터 목록',
  subtitle: '산정에 쓰는 데이터와 기준일을 한 표로 관리합니다.',
  freshnessLabel: '최신 여부',
  freshnessOptions: ['전체', '최신', '갱신 예정일 지남', '빠짐'],
  sourceLabel: '받은 곳',
  sourceOptions: ['전체', '공공데이터포털 API', '파일', '시 내부 자료'],
  upload: '자료 올리기',
  head: ['데이터 ID', '데이터', '제공기관', '받은 곳', '갱신 주기', '기준일', '수집일', '공식 원본 여부', '최신 여부', '결과물에 넣기', '외부 AI로 보내기'],
  past: '과거 기록',
  basisMissing: '기준일 미확인',
  caption: '데이터 목록',
  // 펼친 목록(회차별 원본 목록)
  versionHead: ['회차', '올린 날', '올린 운영자', '파일'],
  // 명세에 빈 표 문구가 없어 사용자 화면 공통 규칙(CM-00 11번)을 따라 지은 문구
  empty: '조건에 맞는 데이터가 없습니다.',
  emptyClear: '필터 모두 지우기',
  failedArea: '데이터 목록',
};

export const UPLOAD = {
  // AD-03
  title: '자료 올리기',
  subtitle: 'API로 받지 못하는 자료와 민원 파일을 올립니다. 출처와 기준일이 없으면 올릴 수 없습니다.',
  data: '자료 이름',
  file: '파일',
  fileHelp: (formats) => `${formats}만 올릴 수 있습니다.`,
  source: '출처',
  sourcePlaceholder: '예: 성남시 도로과 제공',
  basis: '기준일',
  basisHelp: '자료가 기준으로 삼은 날짜입니다. 올린 날이 아닙니다.',
  received: '받은 곳',
  official: '공식 원본 여부',
  period: '민원 접수 기간',
  submit: '파일 올리기',
  errorSourceBasis: '출처와 기준일을 적어야 올릴 수 있습니다.',
  errorFormat: (formats) => `올릴 수 없는 형식입니다. ${formats} 파일을 골라 주세요.`,
  done: (name) => `${name} 파일을 올렸습니다. 검사 결과를 확인해 주세요.`,
  goChecks: '검사 결과 보기',
  recordsTitle: '올린 기록',
  recordsHead: ['올린 날', '올린 운영자', '데이터', '기준일', '출처', '검사 결과'],
  errorsCount: (n) => `오류 ${n}건`,
  recordsNote: 'API로 받는 자료는 정해진 주기에 자동으로 받습니다. 여기에는 파일로 올린 기록만 보입니다.',
  failedArea: '올린 기록',
};

export const CHECKS = {
  // AD-04
  title: '검사 결과',
  subtitle: '검사에서 걸린 자료를 보고 고쳐서 다시 올립니다. 자동으로 고치거나 지우지 않습니다.',
  tabs: { format: '형식 오류', value: '확인이 필요한 값', location: '위치 미확인', group: '같은 시설로 묶지 못한 건' },
  head: ['데이터', '행 번호', '문제', '사유'],
  reupload: '고쳐서 다시 올리기',
  empty: '검사에서 걸린 자료가 없습니다.',
  lowBefore: '민원 위치 낮음 ',
  lowAfter: (cells, changed) => `건 · 상위 ${cells}칸 순위 변화 ${changed}칸`,
  lowNote: '위치가 낮음인 민원은 격자 민원 수에서 뺐습니다. 뺀 경우와 넣은 경우의 상위 순위를 비교한 결과입니다.',
  lowTitle: '위치 낮음 민원',
  lowClose: '위치 낮음 민원 창 닫기',
  failedArea: '검사 결과',
};

export const CLASSIFY = {
  // AD-05
  title: '분류 검수',
  subtitle: 'AI가 나눈 민원 분류 가운데 일부를 확인하고, 틀리면 고칩니다.',
  head: ['민원 요약', '관련 여부', '유형', '판단 근거', '신뢰도'],
  ok: '분류 맞음',
  fix: '분류 고치기',
  empty: '이번에 확인할 표본이 없습니다.',
  doneOk: '맞음',
  doneFix: '고침',
  fixTitle: '분류 고치기',
  fixClose: '분류 고치기 창 닫기',
  fixRelevance: '관련 여부',
  fixType: '유형',
  fixApply: '고친 분류 반영하기',
  confidence: (n) => `${n}%`,
  failedArea: '분류 표본',
};
