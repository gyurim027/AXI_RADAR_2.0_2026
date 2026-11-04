"""실행 다시 하기 (I-06) — 기능정의서 v0.5.3 I-06 "실패하면 원인과 다시 실행 버튼을 보여준다. 다시 실행은 처음부터 한다"
(실패 지점부터 다시 실행은 확장 단계). 화면: 어드민 산정 > 실행 기록(AD-07) 1-2 '로그와 다시 실행'.

85 job_run에는 '무엇을 다시 돌릴지'(입력 파일·옵션)가 남지 않는다. 그래서 기능마다 다시 돌리는 함수를 한 번 등록한다.
등록하지 않은 기능의 실패는 화면에서 다시 실행할 수 없다 (버튼 흐림, canRerun=false) → 담당자가 명령으로 다시 돌린다.

기능 담당자가 할 일 (그 기능 모듈 맨 아래, 서버가 켜질 때 읽히는 곳)
    from app.core.rerun import register_rerun

    def _rerun(ref_table, ref_id, user_id):          # 85의 연결 표·번호로 같은 일을 처음부터. 안에서 track()을 쓴다
        run_engine(int(ref_id))                       # 예: 진규님 산정 — ref_table='priority_run', ref_id=run_id
    register_rerun("ENGINE", _rerun)                  # module 이름은 track(module=...)과 같게

입력이 파일인 기능은 실행 기록 로그에 입력을 남기고 check=로 '이 실행을 다시 돌릴 수 있는지'를 알려 줄 수 있다
(예: app/services/standards/rerun_hooks.py — A-11·A-12).

다시 실행으로 생긴 새 실행 기록에는 첫 단계 로그 '실행 #N(실패)을 처음부터 다시 실행'과 누른 운영자(triggered_by)가 남는다.
"""
from __future__ import annotations

import logging
import threading
from contextvars import ContextVar
from typing import Callable

logger = logging.getLogger("radar.job")
_REG: dict[str, Callable] = {}
_CHECK: dict[str, Callable[[dict], str | None]] = {}   # (선택) 실행 한 건을 다시 돌릴 수 있는지 — 못 하면 이유 글자
_RUNNING: set[tuple] = set()          # 이 서버에서 지금 다시 실행 중인 것 (빠르게 두 번 누르기 막기)
_LOCK = threading.Lock()
_CTX: ContextVar[tuple[int, int | None] | None] = ContextVar("radar_rerun", default=None)
ASYNC = True                          # 뒤에서 돌림. 시험에서는 False


def register_rerun(module: str, fn: Callable[[str | None, str | None, int | None], None], *,
                   check: Callable[[dict], str | None] | None = None) -> None:
    """check(run) (선택): 실행 한 건(로그 포함)을 보고 다시 돌릴 수 없으면 이유를, 되면 None을 돌려준다.
    예: 입력 파일 경로가 실행 기록에 남지 않은 옛 실행 (A-11·A-12)."""
    _REG[module] = fn
    if check is not None:
        _CHECK[module] = check
    else:
        _CHECK.pop(module, None)


def can_rerun(module: str | None) -> bool:
    return bool(module) and module in _REG


def why_not(run: dict) -> str | None:
    """등록된 기능이라도 이 실행 한 건을 다시 돌릴 수 없으면 이유 글자 (없으면 None)."""
    check = _CHECK.get(run.get("module") or "")
    return check(run) if check else None


def current() -> tuple[int, int | None] | None:
    """track()이 읽는다: (다시 실행하는 원래 실행 번호, 누른 운영자) 또는 None"""
    return _CTX.get()


def key_of(run: dict) -> tuple:
    return (run.get("module"), run.get("job_name"), run.get("ref_table"), run.get("ref_id"))


def is_running_here(run: dict) -> bool:
    return key_of(run) in _RUNNING


def _go(run: dict, user_id: int | None, key: tuple) -> None:
    token = _CTX.set((int(run["job_run_id"]), user_id))
    try:
        _REG[run["module"]](run.get("ref_table"), run.get("ref_id"), user_id)
    except Exception as exc:                          # 실패는 그 함수 안의 track()이 85에 '실패'로 남김
        logger.warning("다시 실행이 실패했습니다: #%s %s", run.get("job_run_id"), type(exc).__name__)
    finally:
        _CTX.reset(token)
        with _LOCK:
            _RUNNING.discard(key)


def start(run: dict, user_id: int | None) -> bool:
    """다시 실행 시작. 이미 이 서버에서 같은 것을 돌리는 중이면 False."""
    key = key_of(run)
    with _LOCK:
        if key in _RUNNING:
            return False
        _RUNNING.add(key)
    if ASYNC:
        threading.Thread(target=_go, args=(run, user_id, key), daemon=True).start()
    else:
        _go(run, user_id, key)
    return True
