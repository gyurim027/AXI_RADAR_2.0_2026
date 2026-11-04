import { snakeKeys } from './caseKeys.js';

// AD-04 검사 결과: 위치 미확인 현황과 낮음 민원 (AI-03, 세은). 문서: docs/api/ai03_location.md
// 낮음 민원은 신고에 적힌 위치 글자(locationText)와 좌표(lat·lon)를 서버가 주지만, 화면에 보이지 않으므로 여기서 버린다(2026-10-29 결정).
const dotDate = (iso) => (iso ? String(iso).slice(0, 10).replaceAll('-', '.') : null);

const REFERENCE_A05 = new Set(['A05_DUPLICATE_ROW', 'A05_COORD_RANGE']);

/** 검사 결과 한 줄(data_issue)을 화면 표 모양으로 바꾼다. 위치 글자·원본 값(value_text)은 가져오지 않는다. */
export function toIssueRow(i) {
  // 사본(중복 행)과 좌표 범위 오류는 서버가 A-05로 담지만 진행을 막지 않는 '확인 필요(참고)'다.
  // 좌표 범위 오류 29건은 A-06과 같은 행으로 본다(서버가 처리, 2026-10-29 결정). 그 밖의 A-05만 재업로드로 고칠 '검사 오류'다.
  const reference = REFERENCE_A05.has(i.error_code);
  return {
    id: i.issue_id,
    table: i.table_name || null,
    row: i.source_row_no || null, // 서버가 행 번호를 모르면 0으로 준다. 0은 번호가 아니다.
    rowKey: i.row_key ?? null,
    kind: i.check_name || i.error_code || null,
    reason: i.reason || null,
    // A-05 중 사본(중복 행)은 진행을 막지 않는 '확인 필요(참고)'다. 사본이 아닌 A-05는 재업로드로 고칠 '검사 오류'다 (A-5·A-6).
    label: i.check_fn === 'A-05' ? (reference ? i.review_label || '확인 필요(참고)' : '검사 오류') : null,
    role: i.duplicate_role || null,
  };
}

export function createChecksApi(request) {
  return {
    /** 검사 결과 목록. checkFn은 A-05(형식·빈칸·중복) · A-06(이상한 값) · A-08(같은 시설 묶기). RADAR 운영자만. */
    async listIssues({ checkFn, limit = 50, offset = 0 } = {}) {
      const q = new URLSearchParams({ limit: String(limit), offset: String(offset) });
      if (checkFn) q.set('check_fn', checkFn);
      const d = snakeKeys(await request(`/api/data-issues?${q}`));
      return { total: d.total ?? 0, rows: (d.items || []).map(toIssueRow) };
    },
    /** 표별 좌표 확보 현황(coverage)과 단속 건수 상위 곳(top). RADAR 운영자만. 접근 기록은 남지 않는다. */
    getUnlocated({ limit = 20 } = {}) {
      return request(`/api/ai03/unlocated?${new URLSearchParams({ limit: String(limit) })}`);
    },
    /** 위치 정확도가 낮은 민원. 볼 때마다 접근 기록(민원 점 위치)이 남으므로 화면이 필요할 때 한 번만 부른다. */
    async listLowComplaints({ gu = '', limit = 1000, offset = 0 } = {}) {
      const q = new URLSearchParams({ limit: String(limit), offset: String(offset) });
      if (gu) q.set('gu', gu);
      const d = await request(`/api/ai03/low-complaints?${q}`);
      return {
        total: d.total ?? 0,
        rows: (d.complaints || []).map((c) => ({ id: c.complaintId, date: dotDate(c.receivedDate), gu: c.gu ?? null, dong: c.adminDongName ?? null, method: c.methodKind ?? null })),
      };
    },
  };
}
