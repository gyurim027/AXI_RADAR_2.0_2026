// 후보 주소·대표 지점 표기 (결정 기록 D-59).
// 서버가 주는 값은 위험 위치가 아니라 같은 격자에 연결된 시설 자료의 참고 값이다.
// 어린이집·유치원·보호구역 시설은 이름을 보이지 않고 종류만, 버스정류소는 이름을 보인다.
// 출처 이름은 서버(`location_labels.py`)의 값이다. 모르는 출처의 이름은 보이지 않는다(이름을 보이는 쪽을 먼저 허락하지 않는다).
const NAME_HIDDEN = { '어린이집·유치원': '어린이집 인근', '보호구역 시설': '보호구역 인근' };
const NAME_SHOWN = new Set(['버스정류소']);
const KIND_ONLY = { 횡단보도: '횡단보도 인근', '안전 CCTV': 'CCTV 인근', 보안등: '보안등 인근' };

const clean = (v) => {
  if (typeof v !== 'string') return null;
  const t = v.replace(/\s+/g, ' ').trim();
  return t || null;
};

/**
 * 후보 응답(snake_case)에서 화면에 보일 주소와 대표 지점을 만든다. 값이 없으면 null이다(가짜 값을 만들지 않는다).
 * @returns {{ address: string|null, landmark: string|null }}
 */
export function toLocation(c) {
  const address = clean(c?.address);
  const landmark = clean(c?.landmark);
  const addressSource = clean(c?.address_source);
  const landmarkSource = clean(c?.landmark_source);
  let label = null;
  if (landmark && landmarkSource) {
    if (NAME_HIDDEN[landmarkSource]) label = NAME_HIDDEN[landmarkSource];
    else if (NAME_SHOWN.has(landmarkSource)) label = landmark;
  }
  // 이름이 없어도 주소가 시설 자료에서 왔으면 그 종류로 부른다.
  if (!label && addressSource) label = KIND_ONLY[addressSource] || NAME_HIDDEN[addressSource] || null;
  return { address, landmark: label };
}
