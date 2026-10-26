// DB의 내용 참조를 임의의 가중치·영향 수치로 해석하지 않는다.
export function proposalRow(row, pendingApply = false) {
  return {
    id: row.settingVersionId,
    kind: row.settingKind || (pendingApply ? '담당 부서 표' : ''),
    version: row.versionLabel || '',
    summary: row.contentRef || '저장된 제안 내용이 없습니다.',
    content: row.contentRef,
    date: String(row.proposedAt || row.approvedAt || '').slice(0, 10),
    changes: [],
    status: row.approvalStatus || (pendingApply ? '승인' : '제안'),
    pendingApply,
  };
}

export function createApprovalApi(request) {
  return {
    async list() {
      const [pending, unapplied] = await Promise.all([
        request('/api/approvals?status=제안&limit=500'), request('/api/approvals/unapplied'),
      ]);
      // unapplied에 과거 버전이 포함될 수 있다. 자동 반영하지 않고 preview로 확인한다.
      const rows = new Map((pending.proposals || []).map((r) => [r.settingVersionId, proposalRow(r)]));
      for (const r of unapplied.proposals || []) rows.set(r.settingVersionId, proposalRow(r, true));
      return [...rows.values()];
    },
    async preview(row) {
      if (row.kind !== '담당 부서 표') return { proposalId: row.id, content: row.content, changes: [] };
      const data = await request(`/api/approvals/${encodeURIComponent(row.id)}/preview`);
      return { ...data, proposalId: row.id, changes: [{ field: data.problem, from: data.before, to: data.after }] };
    },
    decide({ id, approve, reason }) {
      return request(`/api/approvals/${encodeURIComponent(id)}/review`, {
        method: 'POST', body: { decision: approve ? '승인' : '돌려보냄', reviewComment: reason?.trim() || null },
      });
    },
    apply({ id }) {
      return request(`/api/approvals/${encodeURIComponent(id)}/apply`, { method: 'POST' });
    },
  };
}

export function approvalErrorMessage(error) {
  const details = error?.details || {};
  const message = error?.message || '요청을 처리하지 못했습니다.';
  if (details.approvalStatus === '승인') {
    return `승인은 기록됐습니다. ${details.departmentApplied === false ? '담당 부서 표는 반영되지 않았습니다.' : '담당 부서 표 반영 여부를 확인해야 합니다.'} ${message}`;
  }
  return message;
}
