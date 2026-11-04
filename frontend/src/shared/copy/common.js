// CM-00 공통 규칙 문구. 키 앞의 번호는 10_2_화면명세_사용자의 CM-00 블록 번호다.
import { withEulReul } from '../utils/format.js';

export const COMMON = {
  // 7 순위 뜻 안내
  rankNotice: 'RADAR 점검 우선순위는 먼저 점검할 곳을 고르는 참고 순위입니다.',

  // 11 빈 목록
  emptyList: '조건에 맞는 점검 후보가 없습니다.',
  // E-1 점검 후보 자체가 없을 때(회차가 없거나 후보 목록이 비어 있음)
  noCandidates: '아직 검토할 점검 후보가 없습니다.',
  noCandidatesHint: 'RADAR 운영팀이 점검 순위 계산을 마치면 이곳에 표시됩니다.',
  // E-2 후보 상세에 근거 자료가 없을 때
  noEvidence: '이 구역에는 표시할 근거 자료가 없습니다. 평가하지 못한 분야를 확인해 주세요.',
  emptyListHint: '필터를 줄여 보세요.',
  emptyListClear: '필터 모두 지우기',

  // 12 불러오기 실패 (%영역 이름%)
  loadFailed: (areaName) => `${withEulReul(areaName)} 불러오지 못했습니다.`, // %영역 이름%을(를)
  loadFailedHint: '잠시 뒤 다시 불러와 주세요. 계속 안 되면 RADAR 운영팀에 알려 주세요.',
  loadFailedRetry: '다시 불러오기',

  // 13 불러오는 중 (%보고서 이름%)
  makingFile: (reportName) => `${reportName} 파일을 만들고 있습니다…`,

  // 14 지도·파일 출처 줄
  sourceMap:
    '출처: 국토지리정보원 수치지형도(1:5,000, 2025).',
  sourceComplaint:
    '민원 출처: 성남데이터넷 연도별 민원 현황(공공누리 제1유형). 주소: 국토교통부 브이월드.',

  // ERR-62 저장·처리 실패 (사용자 화면). 입력한 내용은 지우지 않는다 (POL-024)
  saveFailed: '저장하지 못했습니다. 입력한 내용은 그대로 두었습니다. 잠시 후 다시 시도해 주세요. 계속 실패하면 RADAR 운영팀에 알려 주세요.',
  // ERR-56 보고서 파일 만들기 실패
  fileFailed: '파일을 만들지 못했습니다. 잠시 후 다시 시도해 주세요. 계속 실패하면 RADAR 운영팀에 알려 주세요.',
  // ERR-14~16 접근 안내
  forbiddenGu: '담당 구의 자료만 볼 수 있습니다.',
  forbiddenRole: '이 기능은 현재 계정으로 사용할 수 없습니다. 권한이 필요하면 RADAR 운영팀에 문의해 주세요.',
  notFound: '찾는 화면이 없습니다. 메뉴에서 다시 골라 주세요.',
  goHome: '첫 화면으로 가기',
  notFoundCandidate: '이 구역의 결과가 선택한 점검 후보에 없습니다. 점검 후보 목록에서 다시 골라 주세요.', // ERR-42
  notFoundRun: '선택한 회차를 찾을 수 없습니다. 목록에서 다시 골라 주세요.', // ERR-43
  backToList: '점검 후보 목록으로 돌아가기',

  // 15 민원 내용 표시 (원문은 보이지 않고 가린 요약과 건수만)
  complaintSummary: (total, typeText, recur) =>
    `민원 ${total}건 (${typeText}) · 재발 ${recur}건`,

  // 9 평가하지 못한 분야·조사 안 한 곳
  // 무엇이 빠졌는지 바로 붙인다. 예: '평가하지 못한 분야 1개 (보도 폭)' (UX 고도화 W-8)
  unratedTag: (n, names = []) => `평가하지 못한 분야 ${n}개${names.length ? ` (${names.join(', ')})` : ''}`,
  notSurveyedTag: (fields) => `조사 안 함: ${fields}`,

  // 4 후보 범위 표시
  rangeText: (n) => `이 구역 안의 근거 지점 ${n}곳`,
  rangeUnknown: '이 구역의 근거 지점 정보 없음', // 서버가 근거 지점을 주지 않을 때 (0곳과 구분한다)

  // 5 화면에 쓰는 말
  deptStatusLabel: { A: '확인됨', B: '확인 필요', C: '근거 없음' },
};

/** 지도 오른쪽 아래 지도 자료 줄 (US-01 1-5) */
export const MAP_CREDIT = '지도 자료: 국토지리정보원 수치지형도 (1:5,000, 2025)';
/** 구역을 고르면 주소 좌표를 쓰므로, 같은 자리의 출처 줄이 이 문구로 바뀐다 (브이월드 이용 조건, 10_2 184행) */
export const MAP_COORD_CREDIT = '주소 좌표: 국토교통부 브이월드';
