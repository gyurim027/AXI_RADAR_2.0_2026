// US-01~US-04 화면 문구. 키 앞의 번호는 10_2_화면명세_사용자의 화면·블록 번호다.
// 예) 'US-01.1-4' = US-01 블록 1-4 순위 표

export const LIST = {
  title: '점검 후보', // US-01 0-1
  // 와이어프레임(261019): 제목 위에 범위를 작은 파란 글씨로 쓴다. 구 이름이 위로 올라가서 문구에서는 빠진다.
  eyebrow: (scope) => `성남시 ${scope}`,
  subtitleCity: '3개 구 점검 후보를 함께 봅니다. 우선 점검 대상은 각 구가 정합니다.',
  subtitleDistrict: '점검 후보를 보고 우선 점검 대상을 정해 주세요.',

  // 1 KPI 카드 = 표의 결정 상태 필터 (사용자 결정: 단위 '곳', 이름은 명세 용어)
  kpiLabel: '결정 현황',
  kpiUnit: '곳',
  kpi: { total: '전체', none: '결정 전', target: '우선 점검 대상', hold: '보류', exclude: '제외' },

  // 2-1 필터
  filterButton: '필터',
  filterPanelLabel: '필터 고르기',
  obstacleLabel: '보행 방해요소',
  reliabilityLabel: '신뢰도',
  zoneLabel: '보호구역',
  zoneOptions: ['보호구역 안', '보호구역 밖'],
  complaintLabel: '민원 쏠림',
  complaintOptions: ['재발 있음', '시민 신고 단속 많음'],

  // 2-2 시스템 제안 얼럿 (우선 확인 조건)
  alertTitle: 'RADAR 시스템 제안',
  alertText: (n) => `우선 확인 조건에 맞는 후보가 ${n}곳 있습니다.`,
  alertButton: '맞는 후보만 보기',
  alertActiveText: '우선 확인 조건에 맞는 후보만 보고 있습니다.',
  alertActiveButton: '모든 후보 보기',
  conditionHelp: '점수와 상관없이 먼저 확인할 곳을 고르는 조건입니다. 예: 사고 다발지에 3년 연속 선정.',
  conditionHelpLabel: '우선 확인 조건 뜻 보기',
  conditionTag: (name, ratio) => `${name} · 반영 비율 ${ratio}%`,

  // 2-3 순위 표
  tableCaption: '점검 후보 순위 표',
  candidateHead: '후보', // 주소 + 대표 지점
  needCheck: '현장 확인 필요',
  decisionMenuLabel: (address) => `${address} 결정 상태 바꾸기`,

  // 3 평가하지 못한 구역
  unratedTitle: (n) => `평가하지 못한 구역 (${n}곳)`,
  unratedDesc: '데이터 결측으로 순위를 매기지 못한 항목입니다.',
  unratedHead: ['구역', '수집한 데이터', '수집하지 못한 데이터'],

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
  legendCluster: '숫자 원: 가까운 민원 묶음 (숫자는 건수)',
  clusterNote: '이 칸에는 민원 점이 많아 가까운 점을 묶어 보입니다. 숫자는 민원 건수이고 지도를 확대하면 나뉩니다.',
  mapLabel: '점검 후보 지도',

  // 3-1 구별 비교
  compareButton: '구별 비교 보기',
  compareTitle: '구별 비교',
  compareBody: '구마다 상위 후보 비율과 실제 사고 비율을 나란히 봅니다. 한 구에 후보가 몰렸는지 확인할 때 사용할 수 있습니다.',
  compareHead: ['구', '상위 후보 비율', '보행자 사고 비율', '보정 전 상위 후보 비율'],
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
    6: '⑥ 요청안',
  },

  // 1-1 순위 근거
  basisTitle: '순위 근거',
  basisSub: '이 구역이 순위에 오른 근거입니다.',
  scoreLine: (score, pct) => `점검 필요도 ${score} · 성남시 안 상위 ${pct}%`,
  axisTag: (axes) => `크게 작용한 근거: ${axes}`,
  evidenceHead: ['근거 분야', '근거 자료', '값', '성남시 안 위치', '반영 비율', '기준일', '출처'],
  unratedTag: (name, reason) => `평가하지 못한 분야: ${name} (${reason})`,
  reliabilityTag: (level, reason) => `신뢰도 ${level} · ${reason}`,
  sidewalkHelp: '도면에서 잰 폭이라 실제로 걸을 수 있는 폭과 다를 수 있습니다.',
  sidewalkHelpLabel: '보도 값 도움말 보기',

  // 1-2 민원 신호
  complaintTitle: '민원',
  complaintLine: (types) => types.map((t) => `${t.type} ${t.count}건${t.recur ? ` (재발 ${t.recur})` : ''}`).join(' · '),
  complaintLowAccuracy: (n) => `위치가 정확하지 않은 민원 ${n}건이 들어 있습니다.`, // 낮음 민원도 격자 민원 수에 넣는다 (ISS-033, v0.5.3)
  complaintEmpty: '이번 회차에는 민원 자료가 없습니다. 다른 근거로만 순위를 냈습니다.',

  // 2-1 조문
  articleTitle: '조문',
  articleSub: '이 문제와 관련된 정비 기준과 조문입니다.',
  articleEffective: (d) => `시행 ${d}`,
  articlePending: '시행 전',
  articleEmpty: '이 문제 유형에 맞는 조문을 보유 원문에서 찾지 못했습니다.',

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
  lastNotice: (runName, decision) => `작년(${runName})에 ${decision}로 정한 곳입니다.`,
  lastReason: (reason, memo) => `사유: ${reason || '-'} · 메모: ${memo || '-'}`,
  lastEmpty: '작년에 결정한 기록이 없습니다.',

  // 5-1~5-3 결정 기록
  decisionTitle: '결정 기록',
  decisionSub: '이 후보를 어떻게 할까요? 하나를 고르고 사유를 남겨 주세요.',
  decisionChoices: ['우선 점검 대상', '제외', '보류'],
  reasonModalTitle: (decision) => `${decision} 사유`,
  reasonLabel: '결정 사유',
  reasonPlaceholder: '사유를 골라 주세요',
  reasonOptions: ['이미 정비 계획에 있음', '현장 확인 결과 문제 없음', '다른 부서 소관', '예산·공정 사정', '기타'],
  otherPlaceholder: '예: 재개발 구역과 함께 정비 예정',
  otherLabel: '기타 사유', // 입력 칸의 이름 (스크린 리더용, 명세에 없는 말)
  memoLabel: '메모 (선택)',
  saveDecision: '결정 저장하기',
  reasonRequired: '제외나 보류를 저장하려면 사유를 골라 주세요.',
  otherRequired: '기타 사유를 적어 주세요.',
  historyTitle: '결정 이력',
  historyRow: (date, from, to, org) => `${date} · ${from} → ${to} · ${org}`,
  modalClose: '사유 입력 닫기', // 명세에 없는 닫기 버튼 (확인 필요)

  // 6-1 요청안
  requestTitle: '요청안',
  requestSub: '담당 부서에 보낼 요청 문안과 다음에 할 조치 제안입니다.',
  requestCopy: '요청안 복사하기',
  requestCopied: '요청안을 복사했습니다.', // 명세에 없는 완료 문구 (확인 필요)
  actionTitle: '조치 제안',
  actionDeptCheck: '받는 부서 확인 필요',
  articlePending2: '근거 조문 확인 중',
  needDept: '요청안을 만들려면 담당 부서를 먼저 정해 주세요.',
  pickDept: '담당 부서 정하기',
  requestText: (dept, content, landmark, address, basis, years) =>
    `${dept}에 아래 지점의 확인을 요청드립니다. 요청 내용: ${content}. 위치: ${landmark} 일대 (${address}). 근거: ${basis}. 자료 기준일: ${years}.`,
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
  warning: (n) => `아직 결정하지 않은 후보가 ${n}곳 있습니다. 지금 확정하면 이 후보들은 결정 없이 남습니다.`,
  more: '후보 더 결정하기',
  confirm: '우선 점검 대상 확정',
  doneTitle: (gu) => `${gu} 우선 점검 대상을 확정했습니다.`,
  doneNote: '이제 관할 부서별 보고서를 만들 수 있습니다.',
  doneButton: '관할 부서별 보고서 만들기',
};
