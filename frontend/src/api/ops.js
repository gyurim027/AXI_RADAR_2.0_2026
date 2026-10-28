// 계정 관리(I-01)·접속 기록(I-04)·알림 설정(I-03) 실제 API. 모양은 목업(mocks/adminServer.js)과 같게 맞춘다.
// 서버 오류는 공통 오류 모양으로 오므로, 목업이 { ok:false, code }로 주던 입력 오류만 같은 모양으로 바꿔 화면 코드를 그대로 쓴다.
// 문서: docs/api/admin_accounts.md, docs/ops/I03_alert_mail.md
import { BackendError } from './backend.js';

const CREATE_CODES = { gu_required: 'guRequired', required: 'required', duplicate: 'duplicate' };
// 계정 상태 바꾸기·다시 실행에서 서버가 주는 업무 오류. 화면이 코드로 문구를 고른다 (정의서 12 오류 케이스 추가안).
const STATUS_CODES = { self_change: 'selfChange', account_not_found: 'notFound' };
const RERUN_CODES = { not_failed: 'notFailed', rerun_not_supported: 'notSupported', rerun_input_missing: 'notSupported', already_running: 'alreadyRunning' };

const dotDate = (iso) => (iso ? String(iso).slice(0, 10).replaceAll('-', '.') : null);
const dotDateTime = (iso) => (iso ? `${dotDate(iso)} ${String(iso).slice(11, 16)}`.trim() : null);

/** 서버가 모르는 칸은 null로 온다. 화면이 '-'로 보이게 그대로 두고, 없는 묶음만 빈 값으로 채운다. */
/** 승인 시각이 가장 늦은 것, 같으면 설정 번호가 큰 것 (서버 대시보드 `criteria_card`와 같은 정렬). 시각이 없는 줄은 뒤로 간다. */
export function latestApproved(versions) {
  const at = (x) => String(x.approvedAt ?? '');
  return [...versions].sort((a, b) => (at(a) === at(b) ? b.settingVersionId - a.settingVersionId : at(a) < at(b) ? 1 : -1))[0] ?? null;
}

/** approvedLabel: 지금 쓰는 버전(시 도로과가 승인한 가장 최근 버전)의 이름. 대시보드 응답은 버전 하나만 줘서 getDashboard가 설정 목록에서 찾아 넘긴다. */
export function adaptDashboard(d, approvedLabel = null) {
  return {
    run: { id: d.run?.id ?? null, name: d.run?.name ?? null, status: d.run?.status ?? null },
    next: { key: d.next?.key ?? 'none', text: d.next?.text ?? null, to: d.next?.to ?? null, toLabel: d.next?.toLabel ?? null },
    data: { stale: d.data?.stale ?? null, missing: d.data?.missing ?? null },
    checks: d.checks ? { fix: d.checks.fix ?? null, reference: d.checks.reference ?? null } : null,
    runs: { days: d.runs?.days ?? 30, success: d.runs?.success ?? 0, failure: d.runs?.failure ?? 0, warning: d.runs?.warning ?? 0 },
    approvals: d.approvals ?? null,
    regulations: d.regulations ?? null,
    // 정의서 AD-01 6-1: 지금 쓰는 버전 · 승인 대기 버전. 링크는 승인 대기 버전이 있으면 그 버전, 없으면 지금 쓰는 버전이다.
    criteria: d.criteria ? { approved: approvedLabel, pending: d.criteria.pending ? d.criteria.label ?? String(d.criteria.id) : null, targetId: d.criteria.id } : null,
  };
}

export function createOpsApi(request) {
  return {
    listAccounts() {
      return request('/api/admin/accounts');
    },
    async createAccount({ role, gu, team, name, loginId }) {
      try {
        const r = await request('/api/admin/accounts', { method: 'POST', body: { role, gu: gu || null, team: team || null, name, loginId } });
        // 임시 비밀번호는 이때 한 번만 온다. 화면이 한 번 보여 주고 다시 불러올 수 없다.
        return { ok: true, id: r.id, tempPassword: r.tempPassword, notice: r.notice };
      } catch (e) {
        if (e instanceof BackendError && CREATE_CODES[e.code]) return { ok: false, code: CREATE_CODES[e.code] };
        throw e;
      }
    },
    async setAccountStatus({ id, status, reason }) {
      try {
        await request(`/api/admin/accounts/${encodeURIComponent(id)}/status`, { method: 'PATCH', body: { status, ...(reason ? { reason } : {}) } });
        return { ok: true };
      } catch (e) {
        if (e instanceof BackendError && STATUS_CODES[e.code]) return { ok: false, code: STATUS_CODES[e.code] };
        throw e;
      }
    },
    async listAccess({ days = 30, accountId = '전체', action = '전체' } = {}) {
      const q = new URLSearchParams({ days: String(days) });
      if (accountId && accountId !== '전체') q.set('accountId', accountId);
      if (action && action !== '전체') q.set('action', action);
      const d = await request(`/api/admin/access?${q}`);
      return { ...d, rows: (d.rows || []).map((r) => ({ ...r, key: r.key ?? r.id })) };
    },
    getAlertEmail() {
      return request('/api/admin/alert-email');
    },
    async saveAlertEmail({ value }) {
      try {
        const r = await request('/api/admin/alert-email', { method: 'PUT', body: { value } });
        return { ok: true, value: r.value, message: r.message };
      } catch (e) {
        if (e instanceof BackendError && e.code === 'format') return { ok: false, code: 'format' };
        if (e instanceof BackendError && e.code === 'setting_table_missing') return { ok: false, code: 'tableMissing' };
        throw e;
      }
    },
    async getDashboard() {
      const d = await request('/api/ops/dashboard');
      const c = d.criteria;
      let approved = null;
      if (c && !c.pending) approved = c.label ?? String(c.id);
      else if (c) {
        // 승인 대기 버전이 있으면 대시보드가 그것만 준다. 지금 쓰는 버전은 설정 목록에서 찾는다.
        // 같은 종류(가중치·기준값·우선 확인 조건)끼리만 비교하고, 서버 대시보드처럼 승인 시각이 가장 늦은 것을 고른다.
        try {
          const q = new URLSearchParams({ status: '승인', limit: '500' });
          if (c.kind) q.set('kind', c.kind);
          const v = await request(`/api/settings/versions?${q}`);
          const top = latestApproved(v.versions || []);
          approved = top ? top.versionLabel ?? String(top.settingVersionId) : null;
        } catch {
          approved = null; // 목록을 못 받아도 대시보드는 뜨고 이 칸만 '-'
        }
      }
      return adaptDashboard(d, approved);
    },
    /** 목록 줄에는 로그가 없다. 펼칠 때 getExecution으로 한 건을 불러 채운다. */
    async listExecutions({ days = 30, status = '전체' } = {}) {
      const q = new URLSearchParams({ days: String(days) });
      if (status && status !== '전체') q.set('status', status);
      const d = await request(`/api/ops/runs?${q}`);
      return d.runs || [];
    },
    getExecution({ id }) {
      return request(`/api/ops/runs/${encodeURIComponent(id)}`);
    },
    /** 서버는 실패 알림만 준다 (알림 4종 중 나머지 3종은 서버 API가 없다). */
    async listNotifications() {
      const d = await request('/api/ops/notifications');
      return d.notifications || [];
    },
    markNotificationRead({ id }) {
      return request(`/api/ops/notifications/${encodeURIComponent(id)}/read`, { method: 'POST' });
    },
    /** 담당 부서 표: 현재 표만 온다. 수정안 목록·근거 원문 API는 아직 없어 drafts는 null이다. */
    async getDept() {
      const d = await request('/api/standards/jurisdiction');
      return { current: (d.jurisdiction || []).map(({ id, problem, dept, related, status, basis }) => ({ id, problem, dept, related, status, basis })), drafts: null };
    },
    /** 규정 변경: 변경 목록에 관할 코드별 문제 유형·담당 부서를 붙인다(담당 부서 표를 같이 받아 잇는다). */
    async listRegulationChanges() {
      const [c, j] = await Promise.all([request('/api/standards/changes'), request('/api/standards/jurisdiction')]);
      const jur = new Map((j.jurisdiction || []).map((x) => [x.id, x]));
      return (c.changes || [])
        .map((r) => ({
          id: r.id,
          kind: r.kind,
          name: r.name,
          where: r.where,
          date: dotDate(r.date),
          before: r.before,
          after: r.after,
          detected: dotDateTime(r.detectedAt),
          seen: r.seen,
          juris: r.juris || [],
          jurRows: (r.juris || []).map((id) => ({ id, problem: jur.get(id)?.problem || '-', dept: jur.get(id)?.dept || '-' })),
        }))
        .sort((x, y) => (x.date === y.date ? 0 : !x.date ? 1 : !y.date ? -1 : x.date < y.date ? 1 : -1));
    },
    markRegulationSeen({ id }) {
      return request(`/api/standards/changes/${encodeURIComponent(id)}/seen`, { method: 'POST' });
    },
    async rerunExecution({ id }) {
      try {
        await request(`/api/ops/runs/${encodeURIComponent(id)}/rerun`, { method: 'POST' });
        return { ok: true };
      } catch (e) {
        if (e instanceof BackendError && RERUN_CODES[e.code]) return { ok: false, code: RERUN_CODES[e.code] };
        throw e;
      }
    },
  };
}
