// CM-00 공통 규칙 문구. 키 앞의 번호는 10_2_화면명세_사용자의 CM-00 블록 번호다.
import { withEulReul } from '../utils/format.js';

export const COMMON = {
  // 7 순위 뜻 안내
  rankNotice: 'RADAR 점검 우선순위는 먼저 점검할 곳을 고르는 참고 순위입니다. 공사·예산 순위가 아닙니다.',

  // 11 빈 목록
  emptyList: '조건에 맞는 점검 후보가 없습니다.',
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
    '출처: 국토지리정보원 수치지형도(1:5,000, 2025). 보도 면적·폭은 이 자료로 RADAR가 계산했습니다.',
  sourceComplaint:
    '민원 출처: 성남데이터넷 연도별 민원 현황(공공누리 제1유형). 주소로 찾은 좌표: 국토교통부 브이월드.',

  // 15 민원 내용 표시 (원문은 보이지 않고 가린 요약과 건수만)
  complaintSummary: (total, typeText, recur) =>
    `민원 ${total}건 (${typeText}) · 재발 ${recur}건`,

  // 9 평가하지 못한 분야·조사 안 한 곳
  unratedTag: (n) => `평가하지 못한 분야 ${n}개`,
  notSurveyedTag: (fields) => `조사 안 함: ${fields}`,

  // 4 후보 범위 표시
  rangeText: (n) => `이 구역 안의 근거 지점 ${n}곳`,

  // 5 화면에 쓰는 말
  deptStatusLabel: { A: '확인됨', B: '확인 필요', C: '근거 없음' },
};

/** 지도 오른쪽 아래 지도 자료 줄 (US-01 1-5) */
export const MAP_CREDIT = '지도 자료: 국토지리정보원 수치지형도 (1:5,000, 2025)';
