// 점검 요청서 미리보기(H-01, 진이)의 응답을 사용자 화면이 쓰는 모양으로 바꾼다.
// 서버가 주는 값만 쓴다. 담당 부서가 없으면 서버가 "담당 부서 확인 필요" 묶음으로 준다. 값이 없으면 비워 두고 가짜 값을 만들지 않는다.
// 화면에 보이지 않는 값: limitations·storage 같은 내부 구분(결정 D5). 지금은 1차 범위가 미리보기 전용이라 항상 미리보기로 보인다.
import { snakeKeys } from './caseKeys.js';
import { toLocation } from './locationLabel.js';

const ERR_NOT_READY = 'ERR-45'; // 회차가 확정되기 전(HTTP 409)
const round1 = (v) => (v == null || Number.isNaN(Number(v)) ? null : Math.round(Number(v) * 10) / 10);

function toCandidate(c) {
  return {
    gid: c.gid,
    rank: c.rank_no ?? null,
    score: round1(c.score),
    // 서버가 시설 이름을 숨기고 주지만, 출처를 모르는 이름은 한 번 더 숨긴다(결정 D-59).
    ...toLocation(c),
    evidence: (c.evidence || []).map((e) => e.indicator_name).filter(Boolean),
    requestText: typeof c.request_text === 'string' ? c.request_text : '',
    dataAsOf: c.data_as_of ?? null, // 연결되기 전에는 null이다 → 화면은 '확인 필요'
  };
}

/** H-01 응답(snake_case로 되돌린 것) → 화면 모양. 연습용 화면과 같은 rows(부서, 건수)도 함께 준다. */
export function toAnnualPreview(res) {
  const groups = (res.groups || []).map((g) => {
    const candidates = (g.candidates || []).map(toCandidate);
    return { dept: g.department || '담당 부서 확인 필요', count: candidates.length, candidates };
  });
  return {
    ready: true,
    preview: true,
    count: groups.reduce((n, g) => n + g.count, 0),
    rows: groups.map((g) => ({ dept: g.dept, count: g.count })),
    groups,
  };
}

export function createH01Api(rawRequest) {
  const request = async (path) => snakeKeys(await rawRequest(path));
  return {
    /** 확정 전(409 ERR-45)이면 { ready: false }, 그 밖의 오류는 그대로 던진다. */
    async getPreview({ runId }) {
      try {
        return toAnnualPreview(await request(`/api/h01/runs/${encodeURIComponent(runId)}/preview`));
      } catch (e) {
        if (e?.status === 409 && e?.code === ERR_NOT_READY) return { ready: false, preview: true, count: 0, rows: [], groups: [] };
        throw e;
      }
    },
  };
}
