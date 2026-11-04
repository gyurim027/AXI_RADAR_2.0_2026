// US-05~US-09 보고서 문구. 키 앞의 번호는 10_2_화면명세_사용자의 화면 번호다.

export const DOWNLOAD = {
  title: '파일로 내려받기', // 9-1
  pdf: 'PDF로 내려받기',
  excel: '엑셀로 내려받기',
  // 스크린 리더용 이름에는 대상을 넣는다 (CM-00 6번)
  pdfLabel: (reportName) => `${reportName} PDF로 내려받기`,
  excelLabel: (reportName) => `${reportName} 엑셀로 내려받기`,
};

export const ANNUAL = {
  // US-05
  reportName: '관할 부서별 점검 요청서',
  title: (year) => `${year ? `${year}년 ` : ''}관할 부서별 점검 요청서`,
  subtitle: '확정한 우선 점검 대상을 관할 부서별로 받을 수 있습니다.',
  // 서버 연결 모드는 1차 범위가 미리보기 전용이다(파일 내려받기·자동 발송 없음, 결정 2-14, D5)
  subtitlePreview: '확정한 우선 점검 대상을 관할 부서별로 확인할 수 있습니다.',
  previewTag: '미리보기',
  previewNote: '미리보기입니다. 공식 요청서가 아니며, RADAR는 부서에 자동으로 보내지 않습니다.',
  groupTitle: (dept, n) => `${dept} · 대상 ${n}곳`,
  groupEmpty: '확정한 우선 점검 대상이 없습니다.',
  rankScore: (rank, score) => `${rank != null ? `${rank}위` : '순위 없음'}${score != null ? ` · ${score}점` : ''}`,
  refAddress: '참고 주소',
  evidenceLabel: '점수에 크게 영향을 준 지표',
  requestLabel: '점검 요청 내용',
  dataAsOf: '자료 기준일',
  dataAsOfUnknown: '확인 필요',
  head: ['관할 부서', '대상 수'],
  rowCount: (n) => `대상 ${n}곳`,
  notSend: 'RADAR는 파일을 보내지 않습니다. 받는 부서 담당자를 확인한 뒤 직접 보내 주세요.',
  empty: '3개 구가 모두 우선 점검 대상을 확정한 뒤 만들 수 있습니다.', // 이미 확정한 구에게도 맞는 문구(ERR-45, D6)
  goDecide: '점검 후보 결정하러 가기',
};

export const BASIS = {
  // US-06
  reportName: '구별 우선 점검 근거표',
  title: (year) => `${year ? `${year}년 ` : ''}구별 우선 점검 근거표`,
  subtitle: '구별로 점검 후보와 우선 점검 대상을 왜 골랐는지 정리한 표입니다.',
  head: ['구', '점검 후보', '우선 점검 대상', '주요 근거'],
  count: (n) => `${n}곳`,
  draftTitle: '연간 검토 보고서 초안',
  draftBody: '현황 · 자료 근거 · 관련 기준 · 자료로 모르는 것 · 조치 제안',
  draftEmptyCity: '3개 구가 모두 우선 점검 대상을 확정한 뒤 만들 수 있습니다.',
  draftEmptyDistrict: '3개 구가 모두 우선 점검 대상을 확정하면 만들 수 있습니다.',
};

export const CONDITION = {
  // US-07
  reportName: '우선순위 점수 근거',
  title: (year) => `${year ? `${year}년 ` : ''}우선순위 점수 근거`,
  subtitle: '점검 순위를 계산할 때 사용한 자료와 기준을 남긴 문서입니다.',
  body: (n, version, fields, cond) => `사용한 자료 ${n}종 · 산정 기준 ${version} · 평가하지 못한 분야: ${fields} · 우선 확인 조건 ${cond}개`,
  emptyCity: '3개 구가 모두 우선 점검 대상을 확정하면 만들어집니다.',
  emptyDistrict: '3개 구가 모두 우선 점검 대상을 확정하면 만들어집니다.',
  // 서버 연결 모드: 점수 모델 결과로 만든다. 값을 모르면 '-'로 둔다.
  summary: (version, count, priority) => `산정 기준 ${version || '-'} · 점검 후보 ${count.toLocaleString('ko-KR')}곳 · 우선 확인 조건에 맞는 후보 ${priority.toLocaleString('ko-KR')}곳`,
  scoreTitle: '점수 구성',
  scoreBody: '점검 필요도는 100점 만점입니다. 사고·위험·노출·취약 4개 분야의 지표 9개를 분야별로 모아 계산하며, 평가하지 못한 분야는 빼고 남은 분야의 비율을 유지해 계산합니다.',
  indicatorHead: ['분야', '지표'],
  conditionTitle: '우선 확인 조건',
  conditionBody: '조건은 종합·위험·노출·취약 4개입니다. 각 조건은 충족·미충족·미평가로 나뉘고, 종합 조건을 충족한 후보를 먼저 확인할 후보로 표시합니다. 조건에 맞는지와 점검 후보로 선정됐는지는 서로 다른 값입니다.',
  reliabilityTitle: '자료 신뢰도',
  reliabilityBody: '지표 9개 중 평가할 수 있는 지표의 수로 구분합니다. 높음은 8개 이상, 보통은 6~7개, 낮음은 5개 이하입니다. 위험이 높고 낮은 정도가 아니라 자료를 평가할 수 있는 정도입니다.',
  unratedTitle: '평가하지 못한 분야',
  unratedBody: '자료가 없어 평가하지 못한 분야입니다. 위험이 없다는 뜻이 아니며 0점으로 처리하지 않았습니다.',
  unratedReasons: ['장애물 조사 범위 밖', '탐지 기록이 없고 관측 범위를 확인할 수 없음'],
  unratedCount: (name, n) => `${name} 분야 ${n.toLocaleString('ko-KR')}곳`,
  dataCountUnknown: '사용한 자료 수는 서버에서 아직 받지 못했습니다.',
};

export const PROTECTION = {
  // US-08
  reportName: '보호구역 안팎 비교표',
  title: (year) => `${year ? `${year}년 ` : ''}보호구역 안팎 비교표`,
  subtitle: '보호구역 안과 밖의 상위 후보를 비교한 표입니다. 교통시설팀에 보낼 때 사용할 수 있습니다.',
  head: ['구분', '상위 후보'],
  inside: (n) => `보호구역 안 · ${n}곳`,
  outside: (n) => `보호구역 밖 · ${n}곳`,
};

export const HALF = {
  // US-09
  reportName: '반기 순위 변경 요약',
  title: (year) => `${year ? `${year}년 ` : ''}반기 순위 변경 요약`,
  subtitle: '반기에 바뀐 자료와 그에 따른 순위 변화를 정리했습니다. 확정한 대상은 바뀌지 않습니다.',
  changedTitle: '바뀐 자료',
  changedRow: (name, from, to) => `${name} · 기준일 ${from} → ${to}`,
  changedEmpty: '이번 반기에 바뀐 자료가 없습니다. 연간 점검 순위를 그대로 사용해 주세요.',
  rankTitle: '순위가 크게 바뀐 후보',
  rankRow: (address, from, to) => `${address} · ${from}위 → ${to}위`,
  targetTitle: '근거가 바뀐 우선 점검 대상',
  targetRow: (address, changed) => `${address} · ${changed}`,
};
