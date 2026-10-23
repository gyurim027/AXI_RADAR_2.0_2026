"""AI-05 법령 근거 찾기 API (E-04 관련 조문 · 조치 제안 표 근거 조문 후보)

app.main에서 app.include_router(router)를 추가해야 활성화됩니다.
보유 법령·지침 원문에서 조문을 찾아 원문 그대로 인용합니다. 법 해석·위반 판단은 하지 않습니다.
근거 조문 후보는 운영자가 원문과 대조해 확정합니다(AD-13). 이 API는 DB에 쓰지 않습니다.
"""
from functools import lru_cache

from fastapi import APIRouter, Query

from app.services.ai05.service import LawService


@lru_cache(maxsize=1)
def get_service() -> LawService:
    """색인을 처음 부를 때 한 번만 메모리에 올림 (서버 켜는 시간을 늘리지 않게)"""
    return LawService()


router = APIRouter(prefix="/api/ai05", tags=["AI-05 법령 근거"])


@router.get("/health")
def health():
    svc = get_service()
    return {"status": "ok", "module": "AI-05", "조각 수": len(svc.ix.C), "법령 수": len(svc.ix.by_law),
            "조치 제안 표": svc.actions_source}


@router.get("/related")
def related(problem_type: str | None = Query(None, description="문제 유형 코드. 지금은 법령색인 'RADAR에서 쓴 곳'의 코드(예: T18) — 팀이 유형 목록을 정하면 바뀜"),
            q: str | None = Query(None, description="대응표에 없을 때 쓸 질문 예: 횡단보도 주변 주정차 금지"),
            k: int = 3, include_future: bool = False):
    """후보 상세의 관련 조문 (E-04). ① 대응표 → ② 검색 → ③ '보유 원문에서 못 찾음'"""
    return get_service().related_articles(problem_type, q, k, include_future)


@router.get("/action-basis/{ck_id}")
def action_basis(ck_id: str, k: int = 3):
    """조치 제안 표(81 action_template) 한 줄의 근거 조문 후보 — 운영자가 확인 후 basis_article(근거 조문)에 저장"""
    return get_service().action_basis(ck_id, k)


@router.get("/search")
def search(q: str, k: int = 5, include_future: bool = False):
    """질문형 검색 (어드민·개발 확인용). 못 찾으면 result = '보유 원문에서 못 찾음'"""
    return get_service().search(q, k, include_future)
