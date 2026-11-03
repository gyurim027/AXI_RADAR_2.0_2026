// 역할·구·결정 상태·회차 상태 상수. 기능정의서 04_권한표, 10_2_화면명세_사용자 기준.

export const ROLE = {
  DISTRICT: 'district', // 수정·중원·분당구 (구 도로관리팀)
  CITY: 'city', // 성남시 (시 도로과)
  OPERATOR: 'operator', // RADAR 운영자
};

export const GU_LIST = ['수정구', '중원구', '분당구'];
export const ALL_GU = '3개 구 전체';

export const DECISION = {
  NONE: '결정 전',
  TARGET: '우선 점검 대상',
  EXCLUDE: '제외',
  HOLD: '보류',
};
export const DECISION_LIST = [DECISION.NONE, DECISION.TARGET, DECISION.EXCLUDE, DECISION.HOLD];

export const RUN_STATUS = {
  DRAFT: '산정 중',
  REVIEW: '검토 중',
  FINAL: '확정',
  REF: '참고',
  UNKNOWN: '상태 정보 없음', // 서버가 회차 상태를 주지 않을 때. 가짜 상태를 만들지 않는다 (결정 기록 D-46)
};

export const RELIABILITY = ['높음', '보통', '낮음'];

// 담당 확인 상태 (CM-00 5: 확실도 A·B·C → 확인됨 / 확인 필요 / 근거 없음)
export const DEPT_STATUS = {
  OK: '확인됨',
  CHECK: '확인 필요',
  NONE: '근거 없음',
};

export const PAGE_SIZE = 50;

// 구 도로관리팀의 확정 마감일. DB 회차 표에 마감일 칸이 없어 화면 코드에 둔다 (UX 고도화 5-1 ①, D-7). 점검하는 해 → 마감일
export const CONFIRM_DEADLINES = { 2027: '2027.02.26' };
