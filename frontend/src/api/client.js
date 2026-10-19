// 화면이 데이터를 받는 유일한 길이다. 지금은 src/mocks/server.js(가짜 서버)를 부른다.
// 나중에 Python 백엔드가 붙으면 각 함수 안쪽을 fetch로 바꾼다. 화면 코드는 바꾸지 않는다.
//
// 개발용 도구 (브라우저 콘솔에서):
//   localStorage.setItem('radar.mock.latency', '1500')      // 응답 지연(ms). 1000을 넘으면 회색 뼈대가 보인다
//   localStorage.setItem('radar.mock.fail', 'candidates')   // 이름이 같은 요청을 실패시킨다 (쉼표로 여러 개, all = 전부)
//   localStorage.removeItem('radar.mock.state.v1')          // 가짜 서버의 저장 상태를 처음으로 되돌린다
import { ApiError } from '../mocks/server.js';

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function readSetting(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

/** 가짜 서버 함수를 비동기 API 함수로 감싼다 */
export function mockCall(name, fn) {
  return async (arg) => {
    const latency = Number(readSetting('radar.mock.latency')) || 250;
    await sleep(latency);
    const fail = (readSetting('radar.mock.fail') || '').split(',').map((s) => s.trim());
    if (fail.includes('all') || fail.includes(name)) {
      throw new ApiError('server', '서버 오류');
    }
    return fn(arg);
  };
}

export { ApiError };
