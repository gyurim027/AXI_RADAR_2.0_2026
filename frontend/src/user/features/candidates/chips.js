// 후보 표의 '먼저 볼 이유' 꼬리표. 이름은 짧게, 색은 조건마다 다르게, 개수는 한 줄에 들어가게 센다.
// 전체 이름은 꼬리표의 title과 화면 읽기 이름에 담는다. 색만으로 구분하지 않도록 글자를 늘 같이 쓴다.
export const MAX_CONDITION_CHIPS = 3;

const SHORT = { result: '종합', hazard: '위험', exposure: '노출', vulnerable: '취약', cA: '사고 다발', cB: '민원 재발' };
const TONE = { result: 'accent', hazard: 'high', exposure: 'sky', vulnerable: 'lavender', cA: 'high', cB: 'sky' };

/** @returns {{ shown: {id,label,full,tone}[], hidden: {id,label,full,tone}[] }} */
export function conditionChips(row, conditionMap, max = MAX_CONDITION_CHIPS) {
  const all = (row.conditions || [])
    .filter((id) => conditionMap[id])
    .map((id) => ({ id, label: SHORT[id] || conditionMap[id].name, full: conditionMap[id].name, tone: TONE[id] || 'info' }));
  return { shown: all.slice(0, max), hidden: all.slice(max) };
}
