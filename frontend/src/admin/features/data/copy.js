// 데이터 묶음 문구 (10_3_화면명세_어드민 AD-02~AD-05). 기능정의서 문구가 바뀌면 이 파일만 고친다.

export const LIST = {
  // AD-02
  title: '데이터 목록',
  subtitle: '산정에 쓰는 데이터와 기준일을 한 표로 관리합니다.',
  freshnessLabel: '최신 여부',
  freshnessOptions: ['전체', '최신', '갱신 예정일 지남', '빠짐'],
  sourceLabel: '수집 경로',
  sourceOptions: ['전체', '공공데이터포털 API', '파일', '시 내부 자료'],
  upload: '자료 올리기',
  head: ['데이터 ID', '데이터', '제공기관', '수집 경로', '갱신 주기', '기준일', '수집일', '공식 원본 여부', '최신 여부', '결과물 포함', '외부 AI 전송'],
  // 두 칸의 뜻을 표 위 한 줄로 알린다 (A-2, 5-3 ②)
  help: '수집 경로는 자료를 받은 방법입니다. 공식 원본 여부는 공식 기관이 낸 원본인지를 나타냅니다.',
  past: '과거 기록',
  basisMissing: '기준일 미확인',
  caption: '데이터 목록',
  // 펼친 목록(회차별 원본 목록)
  versionHead: ['회차', '업로드일', '업로드 담당자', '파일'],
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
  received: '수집 경로',
  receivedHelp: '자료를 받은 방법입니다.', // A-2
  officialHelp: '공식 기관이 낸 원본인지를 나타냅니다.',
  official: '공식 원본 여부',
  month: '대상 월',
  monthHelp: '민원 파일은 한 번에 한 달치만 올립니다. 올리는 파일이 어느 달의 민원인지 골라 주세요.', // R-02
  errorMonth: '대상 월을 골라 주세요.',
  submit: '파일 올리기',
  errorSourceBasis: '출처와 기준일을 적어야 올릴 수 있습니다.',
  errorFormat: (formats) => `올릴 수 없는 형식입니다. ${formats} 파일을 골라 주세요.`,
  // 같은 자료를 같은 기준일로 다시 올릴 때: 막지 않고 안내만 한다 (A-03, ISS-049)
  duplicate: (name) => `기준일이 같은 ${name} 파일을 이미 올렸습니다. 올리면 기존 기록은 그대로 두고 새 기록으로 남깁니다.`,
  errorTooLarge: '파일이 너무 큽니다. 100MB 이하로 나눠서 다시 올려 주세요.', // ERR-34
  errorEmpty: '파일에 내용이 없습니다. 파일을 확인한 뒤 다시 올려 주세요.', // ERR-35
  done: (name) => `${name} 파일을 올렸습니다. 검사 결과를 확인해 주세요.`,
  // 민원 파일은 적재 건수를 함께 보인다 (제안, 작업파일 261024 프론트_수정_보완_정리 R-05)
  doneComplaint: (c, month) => `민원 ${month ? `${Number(month.slice(0, 4))}년 ${Number(month.slice(5))}월분 ` : ''}${c.rows.toLocaleString('ko-KR')}건을 올렸습니다. 새로 ${c.new.toLocaleString('ko-KR')}건, 이미 있던 ${c.existing.toLocaleString('ko-KR')}건, 값이 바뀐 ${c.updated.toLocaleString('ko-KR')}건입니다.`,
  busy: '올리는 중입니다. 끝날 때까지 이 창을 닫지 마세요.', // 제안 (R-07)
  goChecks: '검사 결과 보기',
  recordsTitle: '올린 기록',
  recordsHead: ['업로드일', '업로드 담당자', '데이터', '기준일', '출처', '검사 결과'],
  errorsCount: (n) => `오류 ${n}건`,
  recordsNote: 'API로 받는 자료는 정해진 주기에 자동으로 받습니다. 여기에는 파일로 올린 기록만 보입니다.',
  failedArea: '올린 기록',
};

export const CHECKS = {
  // AD-04
  title: '검사 결과',
  subtitle: '검사에서 걸린 자료를 보고 고쳐서 다시 올립니다. 자동으로 고치거나 지우지 않습니다.',
  tabs: { format: '형식 오류', value: '확인이 필요한 값', location: '위치 미확인', group: '시설 묶음 실패' },
  head: ['데이터', '행 번호', '문제', '사유'],
  reupload: '고쳐서 다시 올리기',
  empty: '검사에서 걸린 자료가 없습니다.',
  lowBefore: '민원 위치 낮음 ',
  lowAfter: (cells, changed) => `건 · 상위 ${cells}칸 순위 변화 ${changed}칸`,
  lowNote: '위치 정확도가 낮은 민원도 격자 민원 수에 포함했습니다. 아래는 뺀 경우와 넣은 경우의 상위 순위를 비교한 결과입니다.', // K-2, ISS-033
  lowTitle: '위치 낮음 민원',
  lowClose: '위치 낮음 민원 창 닫기',
  failedArea: '검사 결과',
  // 서버 모드(AI-03 위치 결과). 문구는 제안이다.
  tabNotConnected: '이 탭은 아직 서버와 연결되지 않았습니다.',
  coverageTitle: '표별 좌표 확보 현황',
  coverageCaption: '표별 좌표 확보 현황',
  coverageHead: ['표', '전체 행 수', '좌표 없는 행 수', '좌표 없는 비율'],
  topTitle: '좌표가 없는 단속장소',
  topNote: '단속 건수가 많은 순서로 보여 줍니다.',
  topCaption: '좌표가 없는 단속장소 상위 목록',
  topHead: ['단속장소', '단속 건수'],
  topFoot: (total, shown) => `전체 ${total}곳 중 ${shown}곳`,
  lowUnit: '건',
  lowNoteServer: '위치 정확도가 낮은 민원도 격자 민원 수에 포함했습니다.', // K-2 앞 문장. 순위 비교는 서버에 없어 뺐다
  lowHead: ['접수일', '구', '동', '찾은 방법'],
  lowPartial: (shown, total) => `전체 ${total}건 중 ${shown}건을 보여 줍니다.`,
};

export const CLASSIFY = {
  // AD-05
  title: '민원 분류 검수',
  subtitle: 'AI가 나눈 민원 분류 가운데 일부를 확인하고, 틀리면 고칩니다.',
  head: ['민원 요약', '관련 여부', '유형', '판단 근거', '분류 신뢰도'],
  ok: '분류 맞음',
  fix: '분류 고치기',
  okShort: '맞음', // 행마다 반복되는 버튼은 짧게 쓴다 (U-7). 스크린 리더 이름에는 위 전체 이름을 쓴다.
  fixShort: '고치기',
  empty: '확인할 표본이 없습니다. 민원 분류가 끝나면 확인할 표본이 표시됩니다.', // E-6
  doneOk: '맞음',
  doneFix: '고침',
  fixTitle: '분류 고치기',
  fixClose: '분류 고치기 창 닫기',
  fixRelevance: '관련 여부',
  fixType: '유형',
  fixTypeHelp: '비관련·불명으로 고치면 유형은 비워집니다.',
  errorUnchanged: '고친 분류를 골라 주세요. 분류가 맞다면 분류 맞음을 눌러 주세요.', // ERR-31
  emptyNoPeriod: '이 회차는 민원 접수 기간이 없어 민원 없이 산정했습니다. 확인할 표본이 없습니다.', // ERR-51
  fixApply: '고친 분류 반영하기',
  confidence: (n) => `${n}%`,
  failedArea: '분류 표본',
};
