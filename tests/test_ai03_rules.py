"""AI-03 규칙·검증 시험 — 브이월드·LLM·DB 없이 돈다. (uv sync --extra ai03 이 없으면 건너뜀)"""
import pytest

pytest.importorskip("pandas")
pytest.importorskip("pyproj")

from app.services.ai03 import grid, rules, validate  # noqa: E402


@pytest.mark.parametrize("raw,status", [
    ("서울특별시 강남구 학동로 343", "성남 밖"),
    ("상주영천고속도로", "도로 단위"),
    ("인도위", "위치 없음"),
    ("경기 섬남시 수정구 산성대로", "도로 단위"),
    ("스타벅스 앞 횡단보도", "이름 모호"),
    ("고등동사거리 부근", "이름 모호"),
    ("판교로256번길 환상어린이공원 주변", "후보"),
])
def test_classify_place(raw, status):
    assert rules.classify_place(raw)["status"] == status


def test_core_name_abbr():
    assert rules.core_name("백현중교") == "백현중학교"
    assert rules.core_name("새마을금고") == "새마을금고"          # 금고는 학교가 아님
    assert rules.core_name("갓길정차중") != "갓길정차중학교"


@pytest.mark.parametrize("road,addr,ok", [
    ("산성대로97번길", "경기도 성남시 수정구 산성대로 97", True),     # 갈라지는 자리
    ("산성대로429번길", "경기도 성남시 수정구 산성대로437번길 16", True),
    ("서판교로44길", "경기도 성남시 분당구 서판교로44번길 2", True),
    ("성남대로926번길", "경기도 성남시 분당구 성남대로 165", False),  # 번호가 멀다
    ("대장로8길", "경기도 성남시 분당구 판교대장로6길 10", False),    # 글자 일부만 같음
])
def test_hint_ok_road(road, addr, ok):
    assert validate.hint_ok({"address": addr}, {"road": road, "dong": None}) is ok


def test_name_score_bridge_vs_church():
    assert validate.name_score("둔전교", "둔전교회") == "약함"
    assert validate.name_score("금곡교", "금곡교") == "강함"


def test_volatile_is_held():
    g = validate.grade("규칙+브이월드", "성호지구대", "성호지구대", 37.44, 127.14, "교차로")
    assert g["신뢰도"] == "낮음"


def test_grid_gid_spec_method():
    # 명세서 7장: EPSG:5179로 바꿔 250m로 나눈 칸
    gid, _ = grid.to_gid(37.371498, 127.027058)
    assert gid == "다사58aa30ab"
    assert grid.to_gid(37.0, 126.5)[0] is None                 # 성남 격자 밖
