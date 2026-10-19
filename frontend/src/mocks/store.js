// 가짜 서버의 저장소. 새로 고침해도 남도록 localStorage에 둔다. 비우면 처음 상태로 돌아간다.
import { INITIAL_GU_CONFIRM } from './generate.js';

const KEY = 'radar.mock.state.v1';

function initial() {
  return {
    session: null, // 로그인한 계정 id
    loginFails: {}, // { 아이디: { count, lockedUntil } }
    guConfirm: structuredClone(INITIAL_GU_CONFIRM), // { 회차: { 구: 'YYYY-MM-DD' | null } }
    runStatus: {}, // 3개 구가 모두 확정하면 '확정'으로 바꾼다
    decisions: {}, // { 회차: { gid: { decision, reasonKey, reasonText, memo, history[] } } }
    deptChoice: {}, // { 회차: { gid: 부서 이름 } }
    changeLog: [], // 변경 기록 (G-04)
    notifRead: {}, // { 계정 id: [알림 id] }
    classify: {}, // { 표본 id: { result: '맞음' | '고침', label } }
    proposals: {}, // { 제안 id: { result: '승인' | '반려', reason } }
    accessLog: [], // 접근 기록 (I-04): 내려받기 등
  };
}

let state = null;

function load() {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (raw) return { ...initial(), ...JSON.parse(raw) };
  } catch {
    /* 저장소를 못 쓰는 환경이면 새로 시작한다 */
  }
  return initial();
}

export function getState() {
  if (!state) state = load();
  return state;
}

export function saveState() {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(getState()));
  } catch {
    /* 저장하지 못해도 화면은 계속 쓴다 */
  }
}

export function resetState() {
  state = initial();
  saveState();
}
