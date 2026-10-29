// AD-04 검사 결과: 위치 미확인 현황과 낮음 민원 (AI-03, 세은). 문서: docs/api/ai03_location.md
// 낮음 민원은 신고에 적힌 위치 글자(locationText)와 좌표(lat·lon)를 서버가 주지만, 화면에 보이지 않으므로 여기서 버린다(2026-10-29 결정).
const dotDate = (iso) => (iso ? String(iso).slice(0, 10).replaceAll('-', '.') : null);

export function createChecksApi(request) {
  return {
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
