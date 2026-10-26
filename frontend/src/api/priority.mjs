// 77/78 read-only API contract adapter. No fabricated rank, details or AI text.
const asRun = row => ({
  ...row,
  runId: row.runId ?? row.run_id,
  ruleVersion: row.ruleVersion ?? row.rule_version,
  createdAt: row.createdAt ?? row.created_at,
});
const asExplanation = value => value && typeof value === 'object' ? {
  ...value,
  runId: value.runId ?? value.run_id,
  externalApiCalled: value.externalApiCalled ?? value.external_api_called,
  officialPolicyVerified: value.officialPolicyVerified ?? value.official_policy_verified,
} : null;
const asCandidate = row => ({
  ...row,
  runId: row.runId ?? row.run_id,
  rankNo: row.rankNo ?? row.rank_no ?? null,
  centerLat: row.centerLat ?? row.center_lat ?? null,
  centerLon: row.centerLon ?? row.center_lon ?? null,
  complaintCnt: row.complaintCnt ?? row.complaint_cnt ?? null,
  selectedYn: row.selectedYn ?? row.selected_yn ?? null,
  scoreStatus: row.scoreStatus ?? row.score_status,
  run: row.run ? asRun(row.run) : null,
  explanationContext: asExplanation(row.explanationContext ?? row.explanation_context),
  details: row.details ? {
    ...row.details,
    domainScores: row.details.domainScores ?? row.details.domain_scores ?? null,
    indicatorContributions: row.details.indicatorContributions ?? row.details.indicator_contributions ?? null,
    unevaluatedReasons: row.details.unevaluatedReasons ?? row.details.unevaluated_reasons ?? null,
    confidenceGrade: row.details.confidenceGrade ?? row.details.confidence_grade ?? null,
    scoreExcludingAccidents: row.details.scoreExcludingAccidents ?? row.details.score_excluding_accidents ?? null,
  } : { stored: false },
});
const runId = value => {
  const n = typeof value === 'string' && /^\d+$/.test(value) ? Number(value) : value;
  if (!Number.isSafeInteger(n) || n <= 0) throw new Error('실행회차 식별자가 올바르지 않습니다.');
  return n;
};
export function createPriorityClient(request) {
  const path = run => `/api/priority/runs/${runId(run)}`;
  return {
    halfyearTimeline: async signal => request(`/api/priority/runs/halfyear-timeline`, { signal }),
    runs: async signal => {
      const response = await request('/api/priority/runs?limit=500', { signal });
      if (!Array.isArray(response?.runs)) throw new Error('회차 목록 형식이 올바르지 않습니다.');
      return response.runs.map(asRun);
    },
    candidates: async (run, signal) => {
      const expected = runId(run);
      const all = []; let total;
      do {
        const page = await request(`${path(expected)}/candidates?limit=3000&offset=${all.length}`, { signal });
        if (runId(page?.run?.runId ?? page?.run?.run_id) !== expected ||
            !Number.isInteger(page.total) || page.total < 0 || !Array.isArray(page.candidates)) {
          throw new Error('회차 응답이 일치하지 않습니다.');
        }
        if (total !== undefined && total !== page.total) throw new Error('조회 도중 결과가 변경되었습니다.');
        total = page.total;
        const rows = page.candidates.map(asCandidate);
        if (rows.some(row => runId(row.runId) !== expected || typeof row.gid !== 'string' || !row.gid)) {
          throw new Error('격자 응답이 일치하지 않습니다.');
        }
        if (!rows.length && all.length < total) throw new Error('일부 결과가 누락되었습니다.');
        all.push(...rows);
        if (new Set(all.map(row => row.gid)).size !== all.length || all.length > total) {
          throw new Error('중복 결과가 있습니다.');
        }
      } while (all.length < total);
      return all;
    },
    conditions: (run, signal) => request(`${path(run)}/conditions`, { signal }),
    trustSummary: (run, signal) => request(`${path(run)}/trust-summary`, { signal }),
    comparison: async (before, after, signal) => {
      const oldId = runId(before); const newId = runId(after);
      if (oldId === newId) throw new Error('서로 다른 두 회차를 선택해야 합니다.');
      const all = []; let total;
      do {
        const page = await request(`${path(oldId)}/compare/${newId}?limit=3000&offset=${all.length}`, { signal });
        if (runId(page?.from_run?.run_id) !== oldId || runId(page?.to_run?.run_id) !== newId ||
            !Number.isInteger(page.total) || page.total < 0 || !Array.isArray(page.comparisons)) {
          throw new Error('비교 대상 회차 응답이 일치하지 않습니다.');
        }
        if (total !== undefined && page.total !== total) throw new Error('비교 도중 결과가 변경되었습니다.');
        total = page.total;
        if (!page.comparisons.length && all.length < total) throw new Error('비교 결과 일부가 누락되었습니다.');
        all.push(...page.comparisons);
        if (all.length > total || new Set(all.map(r => r.gid)).size !== all.length) {
          throw new Error('비교 결과에 중복 격자가 있습니다.');
        }
      } while (all.length < total);
      return { comparisons: all, total, interpretation: 'STORED_SCORE_DIFFERENCE_NOT_CAUSAL_IMPROVEMENT' };
    },
    // B11/B13: stored results and explicit unverified execution contract.
    runRollup: async (run, signal) => request(`${path(run)}/rollup`, { signal }),
    runConditions: async (run, signal) => request(`${path(run)}/conditions`, { signal }),
    compareRuns: async (before, after, signal) => request(`${path(before)}/compare/${runId(after)}`, { signal }),
    trustSummary: async (run, signal) => request(`${path(run)}/trust-summary`, { signal }),
    detail: async (run, gid, signal) => {
      const expected = runId(run);
      const data = asCandidate(await request(`${path(expected)}/candidates/${encodeURIComponent(gid)}`, { signal }));
      if (runId(data.runId) !== expected || data.gid !== gid ||
          (data.run && runId(data.run.runId) !== expected) ||
          (data.explanationContext && (runId(data.explanationContext.runId) !== expected || data.explanationContext.gid !== gid))) {
        throw new Error('상세근거 식별자가 일치하지 않습니다.');
      }
      return data;
    },
  };
}
export function displayValue(value) {
  if (value === null || value === undefined) return '미산출';
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return '값 확인 필요';
    if (value !== 0 && Number(value.toFixed(4)) === 0) return `약 ${value > 0 ? '+' : ''}${value.toPrecision(6)}`;
    return value.toFixed(4);
  }
  return String(value);
}

// Same run/grid alone is insufficient: list and detail may be from different data revisions.
// Fail closed rather than showing a score alongside unrelated evidence.
export function assertDetailMatchesList(listRow, detailRow) {
  if (!listRow || !detailRow ||
      runId(listRow.runId) !== runId(detailRow.runId) ||
      listRow.gid !== detailRow.gid ||
      listRow.score !== detailRow.score ||
      listRow.rankNo !== detailRow.rankNo) {
    throw new Error('후보 목록과 상세근거의 저장 결과가 일치하지 않습니다. 회차를 다시 조회해 주세요.');
  }
  return detailRow;
}
