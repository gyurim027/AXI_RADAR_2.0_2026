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
  title: (year) => `${year}년 관할 부서별 점검 요청서`,
  subtitle: '확정한 우선 점검 대상을 관할 부서별로 받을 수 있습니다.',
  head: ['관할 부서', '대상 수'],
  rowCount: (n) => `대상 ${n}곳`,
  notSend: 'RADAR는 파일을 보내지 않습니다. 받는 부서 담당자를 확인한 뒤 직접 보내 주세요.',
  empty: '우선 점검 대상을 확정한 뒤 만들 수 있습니다.',
  goDecide: '점검 후보 결정하러 가기',
};

export const BASIS = {
  // US-06
  reportName: '구별 우선 점검 근거표',
  title: (year) => `${year}년 구별 우선 점검 근거표`,
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
  title: (year) => `${year}년 우선순위 점수 근거`,
  subtitle: '점검 순위를 계산할 때 사용한 자료와 기준을 남긴 문서입니다.',
  body: (n, version, fields, cond) => `사용한 자료 ${n}종 · 산정 기준 ${version} · 평가하지 못한 분야: ${fields} · 우선 확인 조건 ${cond}개`,
  emptyCity: '3개 구가 모두 우선 점검 대상을 확정하면 만들어집니다.',
  emptyDistrict: '3개 구가 모두 우선 점검 대상을 확정하면 만들어집니다.',
};

export const PROTECTION = {
  // US-08
  reportName: '보호구역 안팎 비교표',
  title: (year) => `${year}년 보호구역 안팎 비교표`,
  subtitle: '보호구역 안과 밖의 상위 후보를 비교한 표입니다. 교통시설팀에 보낼 때 사용할 수 있습니다.',
  head: ['구분', '상위 후보'],
  inside: (n) => `보호구역 안 · ${n}곳`,
  outside: (n) => `보호구역 밖 · ${n}곳`,
};

export const HALF = {
  // US-09
  reportName: '반기 순위 변경 요약',
  title: (year) => `${year}년 반기 순위 변경 요약`,
  subtitle: '반기에 바뀐 자료와 그에 따른 순위 변화를 정리했습니다. 확정한 대상은 바뀌지 않습니다.',
  changedTitle: '바뀐 자료',
  changedRow: (name, from, to) => `${name} · 기준일 ${from} → ${to}`,
  changedEmpty: '이번 반기에 바뀐 자료가 없습니다. 연간 점검 순위를 그대로 사용해 주세요.',
  rankTitle: '순위가 크게 바뀐 후보',
  rankRow: (address, from, to) => `${address} · ${from}위 → ${to}위`,
  targetTitle: '근거가 바뀐 우선 점검 대상',
  targetRow: (address, changed) => `${address} · ${changed}`,
};
