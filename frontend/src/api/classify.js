// AD-05 민원 분류 검수 실제 API (C-08). 문서: app/api/c08_review_api.py
// 서버는 표본을 처음 부를 때 만든다. 쓰기는 '맞음'·'고침' 한 건씩 보내는 것뿐이다.

/** 서버 표본 한 줄을 화면 표 모양으로 바꾼다. 모르는 칸은 null로 두어 화면이 '-'로 보이게 한다. */
export function toClassifyItem(x) {
  return {
    id: x.id,
    gu: x.gu ?? null,
    summary: x.summary ?? '-',
    relevance: x.relevance ?? '-',
    label: x.label ?? null,
    keywords: x.keywords ?? '-',
    confidence: x.confidence ?? null,
    done: x.done ?? null,
  };
}

export function createClassifyApi(request) {
  return {
    async list({ runId }) {
      const d = await request(`/api/c08/samples?${new URLSearchParams({ runId: String(runId) })}`);
      return {
        run: d.run ? { id: d.run.id } : null,
        available: d.available !== false, // false면 이 회차에 민원 자료가 없다
        relevance: d.relevance || ['관련', '비관련', '불명'],
        types: d.types || [],
        items: (d.items || []).map(toClassifyItem),
      };
    },
    mark({ id, result, relevance, label }) {
      const body = { result };
      if (result === '고침') {
        body.relevance = relevance;
        body.label = label ?? null;
      }
      return request(`/api/c08/samples/${encodeURIComponent(id)}/review`, { method: 'POST', body });
    },
  };
}
