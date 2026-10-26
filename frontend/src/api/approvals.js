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
  // 연결이 끊겨 처리됐는지 모르면 같은 요청을 다시 보내기 전에 처리 상태를 먼저 확인하게 한다 (POL-024)
  if (error?.code === 'network_error') return `${message} 처리 상태를 다시 확인해 주세요.`;
  if (error?.code === 'proposal_already_reviewed') return '이미 처리된 제안입니다. 목록을 새로 불러왔습니다.'; // ERR-37
  if (error?.code === 'proposal_conflict') return '다른 사용자가 먼저 이 제안을 처리했습니다. 처리 결과를 목록에서 확인해 주세요.'; // ERR-38
  if (error?.code === 'proposal_not_found') return '선택한 제안을 찾을 수 없습니다. 목록을 새로 불러왔으니 다시 골라 주세요.'; // ERR-44
  return message;
}
