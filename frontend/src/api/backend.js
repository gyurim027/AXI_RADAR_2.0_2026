// I-07 실제 연결은 명시적으로 켠 경우에만 사용한다. 실패 시 목업으로 대체하지 않는다.
export const i07BackendEnabled = import.meta.env?.VITE_I07_API === 'true';
export const settingsBackendEnabled = import.meta.env?.VITE_SETTINGS_API === 'true';
export const backendAuthEnabled = i07BackendEnabled || settingsBackendEnabled;
const baseUrl = import.meta.env?.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const sessionKey = 'radar.backend.session.v1';

export class BackendError extends Error {
  constructor(status, code, message, details = {}) {
    super(message);
    this.name = 'BackendError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function createBackendClient({ baseUrl = '', getToken = () => null, fetchImpl = (...args) => fetch(...args), onUnauthorized = () => {} } = {}) {
  return async function request(path, { method = 'GET', body } = {}) {
    const token = getToken();
    const headers = { Accept: 'application/json' };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    let response;
    try {
      response = await fetchImpl(`${baseUrl.replace(/\/$/, '')}${path}`, {
        method, headers, ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      });
    } catch {
      throw new BackendError(0, 'network_error', '서버에 연결하지 못했습니다. 처리 상태를 다시 확인해 주세요.');
    }
    if (response.status === 401) onUnauthorized();
    let data;
    try {
      data = await response.json();
    } catch {
      throw new BackendError(response.status, 'invalid_response', '서버 응답을 확인하지 못했습니다. 처리 상태를 다시 확인해 주세요.');
    }
    if (!response.ok) {
      const error = data?.error || {};
      throw new BackendError(response.status, error.code || 'request_failed', error.message || '요청을 처리하지 못했습니다.', error);
    }
    return data;
  };
}

export function readBackendSession() {
  try {
    return JSON.parse(window.sessionStorage.getItem(sessionKey) || 'null');
  } catch {
    return null;
  }
}

export function saveBackendSession(value) {
  // 보관이 거부되면 로그인 성공으로 표시하지 않는다. 비밀번호는 저장하지 않는다.
  try {
    window.sessionStorage.setItem(sessionKey, JSON.stringify(value));
  } catch {
    throw new BackendError(0, 'session_unavailable', '로그인 정보를 보관할 수 없습니다. 브라우저 설정을 확인해 주세요.');
  }
}

export function clearBackendSession() {
  try { window.sessionStorage.removeItem(sessionKey); } catch { /* 이미 보관하지 못한 경우 */ }
}

export const backendRequest = createBackendClient({
  baseUrl,
  getToken: () => readBackendSession()?.token,
  onUnauthorized: () => {
    clearBackendSession();
    window.dispatchEvent(new Event('radar:session-expired'));
  },
});
