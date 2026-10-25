"""실행 기록 (I-06) + 실패 알림 연결 (I-03), 초안 v0.1 — SQL v2.1의 85 job_run · 86 job_run_log · 71 alert_delivery.

수집·업로드·검사·좌표·분류·산정·설명문·조치 제안·색인을 한 번 돌릴 때마다 85에 한 줄, 중간 단계는 86에 한 줄씩.
실패하면 71 alert_delivery에 RADAR 운영자 알림을 한 줄 남기고, 알림 설정(AD-17)에 메일이 있으면 메일도 보낸다(I-03, app/core/mailer.py). 어드민 실행 로그·대시보드(I-05)가 이 기록을 읽는다.

각 기능(배치·API)에서 쓰는 법
    from app.core.job_run import track, JobFailed

    with track("좌표", "2026 하반기 민원 좌표 붙이기", module="AI-03") as job:
        job.log("주소 2,546건을 읽었습니다")            # 단계 한 줄 (원문·개인정보·SQL X)
        ...
        if 못_찾은_게_많음:
            job.warn("주소 423건은 좌표를 못 붙였습니다")    # 끝 상태 = 경고
        job.rows(2546)                                   # 처리 건수
    # 블록이 끝나면 성공(또는 경고), 예외가 나면 실패로 끝내고 알림을 남긴 뒤 예외를 그대로 다시 던진다.

    raise JobFailed("missing_column", "보도 면적 열이 비어 있음")   # 화면에 보여도 되는 실패 원인을 직접 줄 때
    # 그 밖의 예외는 원인 칸에 '처리 중 오류(<예외 종류>)'만 남는다 (예외 글자에 원문이 섞일 수 있어서)

- 사람이 화면에서 돌렸으면 triggered_by=user["user_id"], API에서 부르면 request_id=request.state.request_id
- 기록에 실패해도(DB가 잠깐 끊김 등) 본래 작업을 막지 않는다. 경고 로그만 남긴다.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger("radar.job")

KINDS = ("수집", "업로드", "검사", "좌표", "분류", "산정", "설명문", "조치 제안", "색인")
RUNNING, SUCCESS, WARNING, FAILURE, SKIPPED = "실행 중", "성공", "경고", "실패", "건너뜀"   # 화면 목업 상태 이름
STATUSES = (RUNNING, SUCCESS, WARNING, FAILURE, SKIPPED)
MAX_TEXT = 300


def _cut(text: str | None, n: int = MAX_TEXT) -> str | None:
    if text is None:
        return None
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


class JobFailed(Exception):
    """화면에 보여도 되는 실패 원인과 코드를 직접 줄 때 쓰는 예외."""

    def __init__(self, code: str, cause: str):
        super().__init__(code)
        self.code, self.cause = code, cause


class JobSkipped(Exception):
    """할 일이 없어 건너뛸 때 (예: 새 파일 없음). 실패가 아니라 '건너뜀'으로 끝난다."""

    def __init__(self, cause: str = ""):
        super().__init__(cause)
        self.cause = cause


# ── 저장소 (DB) ─────────────────────────────────────

class JobStore:
    """85·86·71에 쓰고 읽기. 시험에서는 메모리 저장소로 바꿔 끼운다."""

    def start(self, kind, name, module, ref_table, ref_id, triggered_by, request_id) -> int:
        from app.core import db
        with db.connect() as con:
            with con.cursor() as cur:
                cur.execute(
                    "INSERT INTO job_run (job_kind, job_name, module, ref_table, ref_id, status, triggered_by, request_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (kind, name, module, ref_table, ref_id, RUNNING, triggered_by, request_id))
                run_id = cur.lastrowid
            con.commit()
        return int(run_id)

    def log(self, run_id: int, message: str) -> None:
        from app.core import db
        with db.connect() as con:
            with con.cursor() as cur:
                cur.execute("INSERT INTO job_run_log (job_run_id, message) VALUES (%s, %s)", (run_id, message))
            con.commit()

    def finish(self, run_id, status, row_cnt, error_code, cause, ref_table, ref_id) -> None:
        from app.core import db
        with db.connect() as con:
            with con.cursor() as cur:
                cur.execute(
                    "UPDATE job_run SET status = %s, finished_at = NOW(), row_cnt = %s, error_code = %s, cause = %s, "
                    "ref_table = COALESCE(%s, ref_table), ref_id = COALESCE(%s, ref_id) WHERE job_run_id = %s",
                    (status, row_cnt, error_code, cause, ref_table, ref_id, run_id))
            con.commit()

    def alert_failure(self, run_id: int, message: str) -> None:
        from app.core import db
        with db.connect() as con:
            with con.cursor() as cur:
                cur.execute(
                    "INSERT INTO alert_delivery (job_run_id, channel, recipient_ref, sent_at, delivery_status, message) "
                    "VALUES (%s, '화면', 'RADAR 운영자', NOW(), '보냄', %s)", (run_id, message))
            con.commit()


_store: JobStore = JobStore()


def set_store(store: JobStore) -> None:
    global _store
    _store = store


def get_store() -> JobStore:
    return _store


def _safe(fn, *args):
    try:
        return fn(*args)
    except Exception as exc:                       # 기록 실패가 본래 작업을 막지 않게
        logger.warning("실행 기록을 남기지 못했습니다: %s", type(exc).__name__)
        return None


# ── 쓰는 쪽 ─────────────────────────────────────────

class JobHandle:
    def __init__(self, run_id: int | None):
        self.run_id = run_id
        self._rows: int | None = None
        self._warn: str | None = None
        self._ref: tuple[str | None, str | None] = (None, None)

    def log(self, message: str) -> None:
        if self.run_id is not None:
            _safe(_store.log, self.run_id, _cut(message))

    def rows(self, n: int) -> None:
        self._rows = int(n)

    def warn(self, cause: str) -> None:
        self._warn = _cut(cause)

    def ref(self, table: str, row_id) -> None:
        """실행 중에 생긴 번호를 잇는다 (예: 새로 만든 priority_run.run_id)."""
        self._ref = (table, str(row_id))


@contextmanager
def track(kind: str, name: str, *, module: str | None = None, ref_table: str | None = None, ref_id=None,
          triggered_by: int | None = None, request_id: str | None = None) -> Iterator[JobHandle]:
    if kind not in KINDS:
        raise ValueError(f"모르는 job_kind: {kind} (가능: {', '.join(KINDS)})")
    name = _cut(name, 200)
    run_id = _safe(_store.start, kind, name, module, ref_table, None if ref_id is None else str(ref_id),
                   triggered_by, request_id)
    job = JobHandle(run_id)
    try:
        yield job
    except JobSkipped as exc:
        if run_id is not None:
            _safe(_store.finish, run_id, SKIPPED, job._rows, None, _cut(exc.cause), *job._ref)
        return
    except JobFailed as exc:
        _fail(run_id, name, job, exc.code, _cut(exc.cause))
        raise
    except Exception as exc:
        _fail(run_id, name, job, type(exc).__name__, f"처리 중 오류({type(exc).__name__})")
        raise
    if run_id is not None:
        status = WARNING if job._warn else SUCCESS
        _safe(_store.finish, run_id, status, job._rows, None, job._warn, *job._ref)


def _fail(run_id, name, job, code, cause) -> None:
    if run_id is None:
        return
    _safe(_store.finish, run_id, FAILURE, job._rows, _cut(code, 50), cause, *job._ref)
    _safe(_store.alert_failure, run_id, _cut(f"{name} 실행이 실패했습니다: {cause}"))
    from app.core import mailer                       # RADAR 운영자가 정한 메일로도 (I-03, AD-17). 실패해도 작업·화면 알림은 그대로
    _safe(mailer.notify_failure, run_id, name, cause, lambda m: _safe(_store.log, run_id, _cut(m)))
