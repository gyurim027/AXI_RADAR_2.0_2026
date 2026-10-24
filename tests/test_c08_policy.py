"""C-08 표본과 가중 정확도의 핵심 사례. 실제 DB는 사용하지 않는다."""
from app.services.c08.policy import accuracy, choose_samples


def test_sample_strata_and_stable_order():
    rows = ([{"complaint_id": f"A{i:03}", "relevance": "보행안전 관련", "class_method": "AI"}
             for i in range(20)]
            + [{"complaint_id": f"U{i:03}", "relevance": "불명", "class_method": "AI"}
               for i in range(3)]
            + [{"complaint_id": f"R{i:03}", "relevance": "비관련", "class_method": "규칙"}
               for i in range(8)])
    first, counts = choose_samples(rows, 9)
    second, _ = choose_samples(list(reversed(rows)), 9)
    assert counts == {"AI 판단": 20, "불명": 3, "규칙 판단": 8}
    assert {name: len(items) for name, items in first.items()} == {"AI 판단": 15, "불명": 3, "규칙 판단": 5}
    assert {name: [r["complaint_id"] for r in items] for name, items in first.items()} == {
        name: [r["complaint_id"] for r in items] for name, items in second.items()}


def test_weighted_accuracy_waits_for_every_nonempty_stratum():
    rows = [
        {"gu": "수정구", "sample_group": "AI 판단", "population_count": 10,
         "selected_count": 2, "checked_count": 2, "correct_count": 1},
        {"gu": "수정구", "sample_group": "규칙 판단", "population_count": 90,
         "selected_count": 2, "checked_count": 0, "correct_count": 0},
    ]
    assert accuracy(rows)["status"] == "pending"
    assert accuracy(rows)["accuracy"] is None
    rows[1].update(checked_count=2, correct_count=2)
    result = accuracy(rows)
    assert result["status"] == "complete"
    assert result["accuracy"] == 0.95


def test_human_unknown_and_unattributed_rows_are_not_system_samples():
    rows = [
        {"complaint_id": "A", "relevance": "불명", "class_method": "사람"},
        {"complaint_id": "B", "relevance": "불명", "class_method": None},
        {"complaint_id": "C", "relevance": "불명", "class_method": "AI"},
        {"complaint_id": "D", "relevance": None, "class_method": "AI"},
    ]
    chosen, counts = choose_samples(rows, 7)
    assert counts == {"AI 판단": 0, "불명": 1, "규칙 판단": 0}
    assert [r["complaint_id"] for r in chosen["불명"]] == ["C"]
