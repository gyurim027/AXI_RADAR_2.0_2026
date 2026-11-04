"""62의 산정 설정을 읽는다. 버전 이름 대신 setting_version_id로 식별한다."""
from app.core import db
from app.core.responses import ApiError

KINDS = ("가중치", "기준값", "우선 확인 조건")
COLUMNS = ("setting_version_id, setting_kind, version_label, content_ref, proposed_by, "
           "proposed_at, approval_status, approved_by, approved_at, review_comment")


class SettingsRepository:
    def list_versions(self, kind, status, limit, offset):
        where = ["setting_kind IN (%s, %s, %s)"]
        args = list(KINDS)
        if kind is not None:
            where.append("setting_kind = %s")
            args.append(kind)
        if status is not None:
            where.append("approval_status = %s")
            args.append(status)
        rows = db.read_only(f"SELECT {COLUMNS} FROM setting_version WHERE " + " AND ".join(where) +
                            " ORDER BY setting_version_id DESC LIMIT %s OFFSET %s", [*args, limit + 1, offset])
        return {"versions": rows[:limit], "has_more": len(rows) > limit, "limit": limit, "offset": offset}

    def get_version(self, setting_id):
        rows = db.read_only(f"SELECT {COLUMNS} FROM setting_version WHERE setting_version_id = %s "
                            "AND setting_kind IN (%s, %s, %s)", [setting_id, *KINDS])
        if not rows:
            raise ApiError(404, "setting_not_found", "산정 설정을 찾을 수 없습니다")
        return rows[0]


def get_repository():
    return SettingsRepository()
