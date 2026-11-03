// US-01~US-04 화면 문구. 키 앞의 번호는 10_2_화면명세_사용자의 화면·블록 번호다.
// 예) 'US-01.1-4' = US-01 블록 1-4 순위 표

import { runYear } from '../../../shared/utils/format.js';

export const LIST = {
  title: '점검 후보', // US-01 0-1
  // 와이어프레임(261019): 제목 위에 범위를 작은 파란 글씨로 쓴다. 구 이름이 위로 올라가서 문구에서는 빠진다.
  dataBasis: (year) => `${year}년 자료 기준`, // W-9, D-10
  eyebrow: (scope) => `성남시 ${scope}`,
  subtitleCity: '3개 구 점검 후보를 함께 봅니다. 우선 점검 대상은 각 구가 정합니다.',
  subtitleDistrict: '점검 후보를 보고 우선 점검 대상을 정해 주세요.',

  // 첫 화면 한 줄 안내 (UX 고도화 5-1 ①, 5-2 ①). 마감일은 DB에 칸이 없어 화면 코드에 둔다.
  guideDistrict: (n, deadline) => `결정 전 ${n}곳 · ${deadline ? `${deadline}까지 ` : ''}확정해 주세요.`,
  guideCity: (done, total) => `확정 현황: ${done}/${total}개 구`,

  // 1 KPI 카드 = 표의 결정 상태 필터 (사용자 결정: 단위 '곳', 이름은 명세 용어)
  kpiLabel: '결정 현황',
  kpiUnit: '곳',
  kpi: { total: '전체', none: '결정 전', target: '우선 점검 대상', hold: '보류', exclude: '제외' },

  // 2-1 필터
  filterButton: '필터',
  filterPanelLabel: '필터 고르기',
  obstacleLabel: '보행 방해요소',
  reliabilityLabel: '자료 신뢰도',
  zoneLabel: '보호구역',
  zoneOptions: ['보호구역 안', '보호구역 밖'],
  filterUnavailable: '아직 서버에서 값을 받지 못해 쓸 수 없습니다.',
  complaintLabel: '민원이 몰린 곳',
  complaintHelp: '같은 장소에 여러 해에 걸쳐 민원이 반복된 구역입니다.', // W-16
  complaintHelpLabel: '민원이 몰린 곳 뜻 보기',
  complaintOptions: ['재발 있음', '시민 신고 단속 많음'],

  // 2-2 시스템 제안 얼럿 (우선 확인 조건)
  alertTitle: 'RADAR 시스템 제안',
  alertText: (n) => `우선 확인 조건에 맞는 후보가 ${n}곳 있습니다.`,
  alertButton: '맞는 후보만 보기',
  alertActiveText: '우선 확인 조건에 맞는 후보만 보고 있습니다.',
  alertActiveButton: '모든 후보 보기',
  conditionHelp: '점검 우선순위를 높이는 조건입니다.', // W-7, K-3
  conditionHelpLabel: '우선 확인 조건 뜻 보기',
  // 꼬리표에는 이유만 쓴다. 반영 비율은 상세의 ⓘ에 둔다 (W-7)
  decisionMenuLabel: '결정 상태 바꾸기', // 메뉴 버튼의 화면 읽기 이름 (US-01 1-4)
  conditionTag: (name) => `먼저 볼 이유: ${name}`,
  conditionRatioHelp: (name, ratio) => (ratio == null ? `${name}에 해당해 먼저 확인할 후보로 표시했습니다.` : `${name}의 반영 비율은 ${ratio}%입니다.`),
  conditionStateTitle: '우선 확인 조건 판정',
  conditionState: { Y: '충족', N: '미충족', NULL: '미평가', INVALID: '확인 필요' },
  conditionStateHelpLabel: '미평가 뜻 보기',
  conditionStateHelp: '미평가는 판정에 필요한 자료가 없어 조건을 판정하지 못한 상태입니다. 충족하지 않은 것(미충족)과 다릅니다. 조건에 맞는지와 점검 후보로 선정됐는지는 서로 다른 값입니다.',

  // 2-3 순위 표
  tableCaption: '점검 후보 순위 표',
  candidateHead: '후보', // 주소 + 대표 지점
  needCheck: '현장 확인 필요',

  // 3 평가하지 못한 구역
  unratedTitle: (n) => `평가하지 못한 구역 (${n}곳)`,
  unratedDesc: '자료가 부족해 점검 순위를 매기지 못한 구역입니다.',
  unratedHead: ['구역', '확보한 자료', '조사 안 한 자료'],
  unratedHeadCity: '구', // 시 도로과 표에는 구 열이 앞에 더 있다 (US-01 1-6)

  // 4 바텀 바
  barUndecided: (n) => `아직 결정하지 않은 후보가 ${n}곳 있습니다. 모두 결정한 뒤 확정해 주세요.`,
  barDecided: '모든 후보를 결정했습니다. 우선 점검 대상을 확정해 주세요.',
  barButton: '우선 점검 대상 확정',
  barDone: (gu, date) => `${gu} 우선 점검 대상 확정 완료 · ${date}`,
  barCityButton: '3개 구 확정 현황 보기',

  // 5 지도
  legend: ['점검 필요도 상위 10%', '10~30%', '나머지', '평가하지 못함'],
  legendToggle: (open) => (open ? '범례 접기' : '범례 펼치기'),
  legendChip: '범례 ˅', // 접었을 때 글자 (US-01 1-5)
  // 구역을 골랐을 때 범례 (US-01 1-5, ISS-036·ISS-038)
  legendBasis: (summary) => `이 칸의 근거: ${summary}`,
  legendShapes: '● 민원 (앱 위치) · ○ 민원 (근처 위치) · ■ 다른 근거 지점',
  legendShapesLabel: '채운 원은 민원 앱 위치, 빈 원은 민원 근처 위치, 네모는 다른 근거 지점',
  evidenceHelp: '이 구역의 점검 순위를 높이는 데 영향을 준 주요 지점입니다.', // W-13
  evidenceHelpLabel: '근거 지점 뜻 보기',
  legendCluster: '숫자 원: 가까운 민원 묶음 (숫자는 건수)',
  clusterNote: '민원이 많은 곳은 건수로 모아 볼 수 있습니다. 지도를 확대하면 자세히 볼 수 있습니다.',
  mapLabel: '점검 후보 지도',

  // 3-1 구별 비교
  compareButton: '구별 비교 보기',
  compareTitle: '구별 비교',
  compareBody: '구마다 상위 후보 비율과 실제 사고 비율을 나란히 봅니다. 한 구에 후보가 몰렸는지 확인할 때 사용할 수 있습니다.',
  compareHead: ['구', '상위 후보 비율', '보행자 사고 비율', '보정 전 상위 후보 비율'],
  compareBeforeHelp: '구별 보정을 하기 전에 계산한 상위 후보 비율입니다.', // US-01 3-1 (풀이는 보정 방법 확정 뒤 바뀔 수 있다)
  compareBeforeHelpLabel: '보정 전 상위 후보 비율 뜻 보기',
  compareBack: '순위 표로 돌아가기',
};

export const SUMMARY = {
  // US-02
  close: '요약 닫기',
  evidenceTitle: '주요 근거',
  deptTitle: '담당 부서',
  deptUndecided: '담당 미정',
  detailButton: '근거 자세히 보기',
  explanationFailed: '설명문을 만들지 못했습니다. 아래 근거를 직접 확인해 주세요.',
  rank: (rank) => `${rank}위`,
  title: (address, landmark) => `${address} · ${landmark}`,
};

export const DRAWER = {
  // US-03 0-1
  prev: '◀ 이전 후보',
  next: '다음 후보 ▶',
  closeLabel: '상세 닫기', // 명세에 없는 닫기 버튼 (확인 필요)
  tabs: {
    1: '① 순위 근거',
    2: '② 조문',
    3: '③ 담당 부서',
    4: '④ 작년 결정',
    5: '⑤ 결정 기록',
    6: '⑥ 점검 요청',
  },

  // 1-1 순위 근거
  basisTitle: '순위 근거',
  basisSub: '이 구역의 점검 순위에 영향을 준 근거입니다.',
  scoreLine: (score, pct) => `점검 필요도 ${score}점 · 성남시 내 상위 ${pct}%`,
  scoreHelp: '100점 만점이며, 점수가 높을수록 먼저 점검할 필요가 있습니다.', // W-6
  scoreHelpLabel: '점검 필요도 뜻 보기',
  axisTag: (axes) => `주요 근거: ${axes}`,
  evidenceHead: ['근거 분야', '근거 자료', '값', '성남시 내 순위', '반영 비율', '기준일', '출처'],
  unratedTag: (name, reason) => `평가하지 못한 분야: ${name} (${reason})`,
  unratedHelp: '자료가 없어 평가하지 못한 분야입니다. 위험이 없다는 뜻이 아니며 0점으로 처리하지 않았습니다.', // W-8
  unratedHelpLabel: '평가하지 못한 분야 뜻 보기',
  reliabilityTag: (level, reason) => (reason ? `자료 신뢰도 ${level} · ${reason}` : `자료 신뢰도 ${level}`),
  reliabilityHelp: "지표 9개 중 평가할 수 있는 지표의 수로 구분합니다. 높음은 8개 이상, 보통은 6~7개, 낮음은 5개 이하입니다. 위험이 높고 낮은 정도가 아니라 자료를 평가할 수 있는 정도입니다. '낮음'은 현장 확인이 필요합니다.", // W-10, D-06
  reliabilityHelpLabel: '자료 신뢰도 뜻 보기',
  sidewalkHelp: '도면에서 잰 폭이라 실제로 걸을 수 있는 폭과 다를 수 있습니다.',
  sidewalkHelpLabel: '보도 값 도움말 보기',

  // 1-2 민원 신호
  complaintTitle: '민원',
  complaintTotal: (n) => `민원 ${n}건`, // 유형별 건수를 모를 때 (10_2 CM-00 15번의 앞부분)
  complaintLine: (types) => types.map((t) => `${t.type} ${t.count}건${t.recur ? ` (재발 ${t.recur})` : ''}`).join(' · '),
  complaintLowAccuracy: (n) => `위치를 대략만 알 수 있는 민원 ${n}건도 건수에 포함되어 있습니다.`, // 낮음 민원도 격자 민원 수에 넣는다 (ISS-033, K-1)
  complaintEmpty: '이번 점검 순위에는 민원 자료가 포함되지 않았습니다. 다른 근거만으로 정해진 순위입니다.', // K-6, US-03 1-2

  // 2-1 조문
  articleTitle: '조문',
  articleSub: '이 문제와 관련된 정비 기준과 조문입니다.',
  articleEffective: (d) => `시행 ${d}`,
  articlePending: '시행 전',
  articleEmpty: '이 문제 유형에 맞는 조문을 찾지 못했습니다. RADAR에 등록된 법령 원문에서만 찾습니다.', // K-15

  // 3-1 담당 부서
  deptTitle: '담당 부서',
  deptSubCity: '이 문제를 맡을 부서입니다.',
  deptSubDistrict: '이 문제를 맡을 부서입니다. 확인이 필요하면 직접 정해 주세요.',
  deptReason: (reason) => `판정 이유: ${reason}`,
  deptSelectLabel: '담당 부서',
  deptSelectPlaceholder: '이 후보의 담당 부서를 골라 주세요',

  // 4-1 작년 결정
  lastTitle: '작년 결정',
  lastSub: '작년에 이 구역을 어떻게 결정했는지 봅니다.',
  lastNotice: (runName, decision) => `결정: ${decision} (${runYear(runName)}년 점검 후보)`, // K-4
  lastReason: (reason, memo) => `사유: ${reason || '-'} · 메모: ${memo || '-'}`,
  lastEmpty: '지난 점검 후보에서 결정한 기록이 없습니다.',

  // 5-1~5-3 결정 기록
  decisionTitle: '결정 기록',
  decisionSub: '우선 점검 대상, 제외, 보류 중 하나를 골라 주세요. 제외와 보류는 사유를 함께 남겨야 합니다.', // K-11
  decisionHelp: {
    '우선 점검 대상': '올해 정기 점검에서 먼저 확인하기로 정한 곳입니다.',
    제외: '올해 점검할 필요가 없다고 판단한 곳입니다.',
    보류: '점검이 필요할 수 있지만, 올해는 대상 여부를 결정하지 않은 곳입니다.',
  },
  decisionHelpLabel: (c) => `${c} 뜻 보기`,
  decisionChoices: ['우선 점검 대상', '제외', '보류'],
  reasonModalTitle: (decision) => `${decision} 사유`,
  reasonLabel: '결정 사유',
  reasonPlaceholder: '사유를 골라 주세요',
  // 제외와 보류는 사유 목록을 나눈다 (K-12, 4-4)
  reasonOptionsByDecision: {
    제외: ['현장 확인 결과 문제 없음', '이미 정비 계획에 있음', '다른 부서 소관', '기타'],
    보류: ['예산·공정 사정', '추가 확인 필요', '기타'],
  },
  otherPlaceholder: '예: 재개발 구역과 함께 정비 예정',
  otherLabel: '기타 사유', // 입력 칸의 이름 (스크린 리더용, 명세에 없는 말)
  memoLabel: '메모 (선택)',
  saveDecision: '결정 저장하기',
  alreadyDecided: '이미 결정한 후보입니다. 지금은 결정을 바꿀 수 없습니다.',
  reasonRequired: '제외나 보류를 저장하려면 사유를 골라 주세요.',
  otherRequired: '기타 사유를 적어 주세요.',
  historyTitle: '결정 이력',
  historyRow: (date, from, to, org) => `${date} · ${from} → ${to} · ${org}`,
  modalClose: '사유 입력 닫기', // 명세에 없는 닫기 버튼 (확인 필요)

  // 6-1 요청안
  requestTitle: '점검 요청 내용',
  requestHelp: '담당 부서에 전달할 점검 요청 내용입니다. 보내기 전에 수정할 수 있습니다.',
  requestHelpLabel: '점검 요청 내용 뜻 보기',
  requestSub: '담당 부서에 전달할 점검 요청 내용과 조치 제안입니다.',
  requestCopy: '요청 내용 복사하기',
  requestCopied: '요청 내용을 복사했습니다.', // 명세에 없는 완료 문구 (확인 필요)
  actionTitle: '조치 제안',
  actionDeptCheck: '받는 부서 확인 필요',
  articlePending2: '근거 조문 확인 전',
  needDept: '점검 요청 내용을 만들려면 담당 부서를 먼저 정해 주세요.',
  pickDept: '담당 부서 정하기',
  // 위치 칸: 대표 지점이 '○○ 인근'이면 '일대'를 더 붙이지 않는다. 주소·대표 지점이 없으면 격자 번호로 부른다(가짜 주소를 만들지 않는다).
  requestText: (dept, content, landmark, address, basis, years, fallback = '') => {
    const where = [landmark ? (landmark.endsWith('인근') ? landmark : `${landmark} 일대`) : null, address ? `(${address})` : null].filter(Boolean).join(' ');
    return `${dept}에 아래 지점의 확인을 요청드립니다. 요청 내용: ${content}. 위치: ${where || fallback}. 근거: ${basis}. 자료 기준일: ${years}.`;
  },
  locationNote: '주소는 같은 격자에 연결된 시설 자료를 참고한 값입니다.',
};

export const CONFIRM = {
  // US-04 시 도로과
  cityTitle: '3개 구 우선 점검 대상 확정 현황',
  cityStatus: (gu, done, date) => `${gu} ${done ? `확정 완료 ${date}` : '확정 전'}`,
  close: '닫기',
  // US-04 도로관리팀
  title: (gu) => `${gu} 우선 점검 대상을 확정할까요?`,
  sub: (gu) => `확정하면 ${gu} 결정은 더 고칠 수 없습니다.`,
  numbers: (c) => `결정 전 ${c.none}곳 · 우선 점검 대상 ${c.target}곳 · 보류 ${c.hold}곳 · 제외 ${c.exclude}곳`,
  warning: (n) => `아직 결정하지 않은 후보가 ${n}곳 있습니다. 지금 확정하면 이 후보들은 우선 점검 대상에 들어가지 않아 점검 요청서에 포함되지 않습니다.`,
  more: '후보 더 결정하기',
  confirm: '우선 점검 대상 확정',
  doneTitle: (gu) => `${gu} 우선 점검 대상을 확정했습니다.`,
  doneNote: '관할 부서별 점검 요청서는 회차가 확정된 뒤에 만들 수 있습니다.',
  doneButton: '관할 부서별 점검 요청서 만들기',
};
