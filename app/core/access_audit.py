"""접근 기록 (I-04, W05-03 골격 8번, 초안 v0.1) — 70 access_audit, POL-022.

사람이 아니라 서버가 자동으로 남긴다. 추가만 하고 수정·삭제하는 함수는 만들지 않는다(고시 제8조③). 2년 이상 보관.
한 줄 = actor_ref(계정) · resource_kind(무엇을) · resource_key(어디를) · client_ip · access_reason(업무 목적)
번호·시각(accessed_at)은 DB가 채운다.

기능 API에서 쓰는 법
    from fastapi import Depends, Request
    from app.core.auth import current_user
    from app.core import access_audit as audit

    # 1) 민원 점 위치 (지도에서 구역을 누를 때): 로그인 한 번 동안 구·업무 목적마다 한 줄만
    @router.get("/complaint-points")
    def points(gid: str, gu: str, request: Request, user: dict = Depends(current_user)):
        audit.complaint_points(request, user, gu, reason="점검 후보 검토")   # 다른 구면 403도 여기서
        ...

    # 2) 파일 내려받기·결정·승인·설정 변경: 할 때마다 한 줄
    audit.record(request, user, audit.DOWNLOAD, key="2026 상반기 구별 우선 점검 근거표")

로그인은 /api/auth/login이 자동으로 남긴다.
"""
from __future__ import annotations

import logging

from fastapi import Request

from app.core.auth import check_gu, client_ip

logger = logging.getLogger("radar.audit")

# resource_kind 값 (POL-022 대상). 새 값이 필요하면 은경에게 요청
LOGIN = "로그인"
COMPLAINT_POINTS = "민원 점 위치"
DOWNLOAD = "파일 내려받기"
DECISION = "결정"
APPROVAL = "승인"
SETTING_CHANGE = "설정 변경"
KINDS = (LOGIN, COMPLAINT_POINTS, DOWNLOAD, DECISION, APPROVAL, SETTING_CHANGE)


class AuditStore:
    """70 access_audit에 쓰기. 시험에서는 MemoryAuditStore로 바꿔 끼운다."""

    def insert(self, actor_ref: int, kind: str, key: str | None, ip: str | None, reason: str | None) -> None:
        from app.core import db
        with db.connect() as con:
            with con.cursor() as cur:
                cur.execute("INSERT INTO access_audit (actor_ref, resource_kind, resource_key, client_ip, access_reason) "
                            "VALUES (%s, %s, %s, %s, %s)", (actor_ref, kind, key, ip, reason))
            con.commit()

    def insert_in_transaction(self, con, actor_ref: int, kind: str, key: str | None,
                              ip: str | None, reason: str | None) -> None:
        """호출자의 거래에 기록한다. commit/rollback/close는 호출자 책임이다."""
        with con.cursor() as cur:
            cur.execute("INSERT INTO access_audit (actor_ref, resource_kind, resource_key, client_ip, access_reason) "
                        "VALUES (%s, %s, %s, %s, %s)", (actor_ref, kind, key, ip, reason))

    def exists_since(self, actor_ref: int, kind: str, key: str | None, reason: str | None, since_epoch: int) -> bool:
        from app.core import db
        rows = db.read_only(
            "SELECT 1 AS hit FROM access_audit WHERE actor_ref = %s AND resource_kind = %s AND resource_key <=> %s "
            "AND access_reason <=> %s AND accessed_at >= FROM_UNIXTIME(%s) LIMIT 1",
            (actor_ref, kind, key, reason, since_epoch))
        return bool(rows)


_store: AuditStore = AuditStore()


def set_store(store: AuditStore) -> None:
    """시험용: 저장소를 바꿔 끼운다."""
    global _store
    _store = store


def get_store() -> AuditStore:
    return _store


def record(request: Request, user: dict, kind: str, key: str | None = None, reason: str | None = None, *, connection=None) -> None:
    """할 때마다 한 줄. 실패는 호출자에게 전달한다.

    connection이 있으면 그 거래에 기록하고 commit하지 않는다.
    없으면 기존처럼 독립 연결로 저장한다. 기존 호출의 동작은 유지한다.
    """
    if kind not in KINDS:
        raise ValueError(f"모르는 resource_kind: {kind}")
    if connection is None:
        _store.insert(user["user_id"], kind, key, client_ip(request), reason)
    else:
        _store.insert_in_transaction(connection, user["user_id"], kind, key, client_ip(request), reason)


def complaint_points(request: Request, user: dict, gu: str, reason: str) -> bool:
    """민원 점 위치: 로그인 한 번 동안 같은 구·같은 업무 목적이면 한 줄만. 새로 남겼으면 True.

    다른 구(구 도로관리팀)면 403. 같은 로그인인지는 토큰 발급 시각(login_at) 뒤에 같은 줄이 있는지로 본다.
    """
    check_gu(user, gu)
    if _store.exists_since(user["user_id"], COMPLAINT_POINTS, gu, reason, user["login_at"]):
        return False
    _store.insert(user["user_id"], COMPLAINT_POINTS, gu, client_ip(request), reason)
    return True
