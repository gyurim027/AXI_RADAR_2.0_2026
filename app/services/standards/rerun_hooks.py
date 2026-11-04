"""A-11 법령 개정 확인 · A-12 업무분장 변경 확인을 운영 화면에서 '다시 실행'(I-06, AD-07 1-2)할 수 있게 등록한다.

기능정의서 v0.5.4 I-06: "실패하면 원인과 다시 실행 버튼을 보여준다. 다시 실행은 처음부터 한다."
85 job_run에는 입력(원문 폴더·비교할 두 판)이 남지 않는다. 그래서 두 명령은 실행을 시작할 때
86 job_run_log에 '다시 실행용 입력: [...]' 한 줄을 남기고(경로는 절대 경로로 바꿔서), 다시 실행할 때 그 줄을 읽어
같은 명령을 같은 입력으로 처음부터 돌린다. 새 실행 기록에는 '실행 #N(실패)을 처음부터 다시 실행'과 누른 운영자가 남는다.

- 이 줄이 없는 옛 실행(이 기능 전에 돌린 것)은 화면에서 다시 실행할 수 없다 → 409 rerun_input_missing, 명령으로 다시 돌린다.
- 다시 실행은 서버가 켜진 PC에서 돈다. 입력 폴더·파일이 그 PC에 있어야 한다 (없으면 그 실행이 '실패'로 남는다).
- 넣는 글자는 파일 경로와 옵션뿐이다 (원문·민원·개인정보 없음).
서버가 켜질 때 app/api/standards_api.py가 이 파일을 읽어 등록한다.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Iterable

from app.core import rerun
from app.core.job_run import MAX_STRUCTURED_TEXT

PREFIX = "다시 실행용 입력: "
SCRIPTS = {"A-11": "scripts.standards_check_law_revision", "A-12": "scripts.standards_compare_duty"}
PATH_OPTS = {"A-11": ("--new-src", "--new-chunks"), "A-12": ("--old", "--new", "--jurisdiction")}


def absolute(argv: Iterable[str], path_opts: Iterable[str]) -> list[str]:
    """경로 옵션 바로 뒤 값을 절대 경로로 바꾼다 (다시 실행할 때 서버의 현재 폴더와 상관없게)."""
    out, opts = list(argv), set(path_opts)
    for i, a in enumerate(out):
        if a in opts and i + 1 < len(out):
            out[i + 1] = str(Path(out[i + 1]).expanduser().resolve())
        elif "=" in a and a.split("=", 1)[0] in opts:
            k, v = a.split("=", 1)
            out[i] = f"{k}={Path(v).expanduser().resolve()}"
    return out


def remember(job, module: str, argv: Iterable[str]) -> None:
    """실행 시작 때 부른다: 86에 다시 실행용 입력 한 줄.

    job.log 기본 300자 자르기를 쓰면 경로가 길 때 JSON이 깨져 saved_argv()가
    못 읽는다(11/4 발견). 되읽어 parsing해야 하는 구조화 데이터라 더 큰 한도로 남긴다."""
    job.log(PREFIX + json.dumps(absolute(argv, PATH_OPTS.get(module, ())), ensure_ascii=False),
            max_len=MAX_STRUCTURED_TEXT)


def saved_argv(run: dict) -> list[str] | None:
    """실행 기록(로그 포함)에서 다시 실행용 입력을 찾는다. 여러 줄이면 맨 처음 줄."""
    for line in run.get("logs") or []:
        msg = line.get("message") if isinstance(line, dict) else str(line)
        if msg and msg.startswith(PREFIX):
            try:
                argv = json.loads(msg[len(PREFIX):])
            except ValueError:
                return None
            return [str(a) for a in argv] if isinstance(argv, list) else None
    return None


def _check(run: dict) -> str | None:
    if "logs" not in run:                       # 목록 화면 (로그 없이 읽음) → 누를 때 다시 본다
        return None
    return None if saved_argv(run) is not None else "실행 기록에 입력(파일 경로)이 남아 있지 않음"


def _runner(module: str):
    def again(_ref_table, _ref_id, _user_id) -> None:
        orig = rerun.current()
        from app.services.ops.repository import get_repository
        run = get_repository().get_run(orig[0]) if orig else None
        argv = saved_argv(run or {})
        if argv is None:
            raise RuntimeError("다시 실행용 입력이 없습니다")
        try:
            importlib.import_module(SCRIPTS[module]).main(argv)
        except SystemExit as exc:               # 명령이 SystemExit로 멈춰도(읽을 수 없는 파일 형식 등) 서버 스레드는 안전하게
            raise RuntimeError(f"명령이 멈췄습니다: {exc}") from None
    return again


def register() -> None:
    for module in SCRIPTS:
        rerun.register_rerun(module, _runner(module), check=_check)


register()
