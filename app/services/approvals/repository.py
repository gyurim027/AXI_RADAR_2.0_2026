"""62 제안 검토: 행 잠금·조건부 전이·감사를 한 거래로 처리한다.

부서표는 은경 apply_approved의 계약대로 승인·감사 커밋 뒤 별도 거래로 반영한다.
가중치·기준값·우선 확인 조건 승인은 버전 승인만 하며 산정/재계산을 실행하지 않는다.
"""
from app.core import access_audit as audit, db
from app.core.responses import ApiError
from app.services.standards.apply import ApplyError, apply_approved, preview, unapplied

KINDS = ("가중치", "기준값", "우선 확인 조건", "담당 부서 표")
STATUSES = ("제안", "승인", "돌려보냄")
COLUMNS = ("setting_version_id, setting_kind, version_label, content_ref, proposed_by, "
           "proposed_at, approval_status, approved_by, approved_at, review_comment")


class ApprovalRepository:
    def list_proposals(self, status: str, limit: int):
        return db.read_only(
            f"SELECT {COLUMNS} FROM setting_version WHERE approval_status = %s "
            "ORDER BY proposed_at, setting_version_id LIMIT %s", (status, limit))

    def get_proposal(self, proposal_id: int):
        rows = db.read_only(f"SELECT {COLUMNS} FROM setting_version WHERE setting_version_id = %s", (proposal_id,))
        if not rows:
            raise ApiError(404, "proposal_not_found", "제안을 찾을 수 없습니다")
        return rows[0]

    def decide(self, proposal_id: int, decision: str, comment: str | None, request, user: dict):
        # 서비스 직접 호출도 인증 문맥의 시 도로과 역할을 확인한다.
        if user.get("role") != "city":
            raise ApiError(403, "forbidden_role", "시 도로과만 제안을 처리할 수 있습니다")
        if decision not in ("승인", "돌려보냄"):
            raise ApiError(422, "invalid_decision", "승인 또는 돌려보냄을 선택하세요")
        comment = comment.strip() if comment else None
        if decision == "돌려보냄" and not comment:
            raise ApiError(422, "review_comment_required", "돌려보내는 사유를 적어 주세요")
        if comment and len(comment) > 255:
            raise ApiError(422, "review_comment_too_long", "검토 의견은 255자까지 입력할 수 있습니다")
        with db.connect() as con:
            with con.cursor() as cur:
                cur.execute(f"SELECT {COLUMNS} FROM setting_version WHERE setting_version_id = %s FOR UPDATE",
                            (proposal_id,))
                row = cur.fetchone()
                if not row:
                    raise ApiError(404, "proposal_not_found", "제안을 찾을 수 없습니다")
                if row["approval_status"] != "제안":
                    raise ApiError(409, "proposal_already_reviewed", "이미 처리됐거나 제안 상태가 아닙니다")
                if row["setting_kind"] not in KINDS:
                    raise ApiError(422, "unsupported_setting_kind", "지원하지 않는 설정 종류입니다")
                cur.execute(
                    "UPDATE setting_version SET approval_status = %s, approved_by = %s, "
                    "approved_at = CURRENT_TIMESTAMP, review_comment = %s "
                    "WHERE setting_version_id = %s AND approval_status = %s",
                    (decision, user["user_id"], comment, proposal_id, "제안"))
                if cur.rowcount != 1:
                    raise ApiError(409, "proposal_conflict", "다른 요청이 먼저 제안을 처리했습니다")
                cur.execute(f"SELECT {COLUMNS} FROM setting_version WHERE setting_version_id = %s", (proposal_id,))
                result = cur.fetchone()
            # 의견 원문은 62에 보존한다. 70의 255자 제한을 넘기지 않도록 감사에는 결정만 기록한다.
            audit.record(request, user, audit.APPROVAL, key=f"setting_version:{proposal_id}",
                         reason=decision, connection=con)
            con.commit()
        applied = None
        if decision == "승인" and row["setting_kind"] == "담당 부서 표":
            applied = self._apply(proposal_id, user, known_approved=True)
        return {"ok": True, "proposal": result, "department_applied": bool(applied),
                "application": applied, "recalculation_started": False}

    def preview_department(self, proposal_id: int):
        try:
            return preview(proposal_id)
        except ApplyError as exc:
            raise ApiError(exc.status, exc.code, exc.message) from None

    def pending_department(self):
        return unapplied()

    def retry_department(self, proposal_id: int, user: dict):
        if user.get("role") != "city":
            raise ApiError(403, "forbidden_role", "시 도로과만 다시 반영할 수 있습니다")
        # apply_approved가 승인 상태·종류·이미 반영 여부를 직접 확인한다.
        return {"ok": True, "department_applied": True, "application": self._apply(proposal_id, user)}

    def _apply(self, proposal_id: int, user: dict, *, known_approved: bool = False):
        try:
            return apply_approved(proposal_id, user["user_id"])
        except ApplyError as exc:
            # 여기서는 승인 거래가 이미 끝났다. 승인 기록을 제안으로 되돌리지 않는다.
            # retry 경로에서 not_approved도 발생할 수 있어 현재 상태를 조회한다.
            row = self.get_proposal(proposal_id)
            raise ApiError(exc.status, exc.code, exc.message, {
                "approval_status": row["approval_status"], "department_applied": False,
                "apply_status": "실패", "retry_url": f"/api/approvals/{proposal_id}/apply",
            }) from None
        except Exception:
            # commit 응답 유실이면 실제 반영 여부가 불명확하다. 재시도는 멱등 처리로 재확인한다.
            raise ApiError(503, "department_apply_failed", "부서표 반영 상태를 확인한 뒤 다시 시도하세요", {
                "approval_status": "승인" if known_approved else None,
                "department_applied": None, "apply_status": "확인 필요",
                "retry_url": f"/api/approvals/{proposal_id}/apply",
            }) from None


def get_repository():
    return ApprovalRepository()
