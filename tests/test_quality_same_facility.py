"""A-08 같은 시설 묶기 — 정확도 '낮음' 좌표는 ③(같은 자리·다른 이름)에서 뺀다 (DB 없이 가짜 표로 시험)."""
import pandas as pd

import scripts.quality_same_facility as A

BASE = dict(lat=37.40, lon=127.12)


def table(rows):
    d = pd.DataFrame([{**BASE, **r} for r in rows])
    d.insert(0, "row_id", range(1, len(d) + 1))
    return d


def kinds(d):
    return [t for _, t, *_ in A.groups_in("src_parking_enforce_place", d, "row_id")]


def test_low_accuracy_points_are_not_grouped_as_same_spot_different_name():
    d = table([{"enforce_place": "미금역 2번출구", "coord_accuracy": "낮음 (AI-03 장소 이름 검색)"},
               {"enforce_place": "미금역 3번출구", "coord_accuracy": "낮음 (AI-03 장소 이름 검색)"}])
    assert not any(k.startswith("③") for k in kinds(d))


def test_one_low_one_normal_is_also_left_out():
    d = table([{"enforce_place": "가 정류장", "coord_accuracy": "낮음 (장소 이름 검색)"},
               {"enforce_place": "나 정류장", "coord_accuracy": "보통 (주소)"}])
    assert not any(k.startswith("③") for k in kinds(d))


def test_two_normal_points_with_different_names_still_flagged():
    d = table([{"enforce_place": "가 정류장", "coord_accuracy": "보통 (주소)"},
               {"enforce_place": "나 정류장", "coord_accuracy": "보통 (주소)"}])
    assert [k[:1] for k in kinds(d)] == ["③"]


def test_same_name_is_still_grouped_even_with_low_accuracy():
    d = table([{"enforce_place": "서현역 주변", "enforce_cnt": 10, "coord_accuracy": "낮음 (장소 이름 검색)"},
               {"enforce_place": "서현역 주변", "enforce_cnt": 20, "coord_accuracy": "낮음 (장소 이름 검색)"}])
    assert [k[:1] for k in kinds(d)] == ["②"]            # 이름이 같으면 이름이 근거라 낮음이어도 ②로 묶는다 (내용이 완전히 같으면 ①)


def test_table_without_accuracy_column_behaves_as_before():
    d = table([{"enforce_place": "가"}, {"enforce_place": "나"}])
    assert [k[:1] for k in kinds(d)] == ["③"]


def test_skipped_pairs_are_counted_for_the_summary_line():
    A.SKIP_LOW.clear()
    d = table([{"enforce_place": "가", "coord_accuracy": "낮음 (x)"}, {"enforce_place": "나", "coord_accuracy": "낮음 (x)"},
               {"enforce_place": "다", "coord_accuracy": "낮음 (x)"}])
    kinds(d)
    assert A.SKIP_LOW == {"src_parking_enforce_place": 3}   # 세 점이 한 자리 → 쌍 3개
