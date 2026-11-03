// 서버는 /api/ 응답의 영문 snake_case 키를 camelCase로 바꿔 준다(값은 그대로). 어댑터는 서버 원래 이름(snake_case)으로 읽으려고 되돌린다.
// 지표 코드(cond_blind_spot_cnt)처럼 값 안의 키도 같이 바뀌므로 되돌려야 이름표 표와 맞는다.
const toSnake = (key) => key.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toLowerCase();

export function snakeKeys(value) {
  if (Array.isArray(value)) return value.map(snakeKeys);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k, v]) => [toSnake(k), snakeKeys(v)]));
  return value;
}
