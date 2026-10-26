// 계정 관리(I-01)·접속 기록(I-04)·알림 설정(I-03) 실제 API. 모양은 목업(mocks/adminServer.js)과 같게 맞춘다.
// 서버 오류는 공통 오류 모양으로 오므로, 목업이 { ok:false, code }로 주던 입력 오류만 같은 모양으로 바꿔 화면 코드를 그대로 쓴다.
// 문서: docs/api/admin_accounts.md, docs/ops/I03_alert_mail.md
import { BackendError } from './backend.js';

const CREATE_CODES = { gu_required: 'guRequired', required: 'required', duplicate: 'duplicate' };

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
    setAccountStatus({ id, status, reason }) {
      return request(`/api/admin/accounts/${encodeURIComponent(id)}/status`, { method: 'PATCH', body: { status, ...(reason ? { reason } : {}) } });
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
        throw e;
      }
    },
  };
}
