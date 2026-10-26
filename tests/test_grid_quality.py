"""격자·검사 시험 (B-02 · C-07 · A-06 · A-08 공통 부품) — DB·원본 공간 파일 없이 작은 CSV로 돈다."""
import pytest

pd = pytest.importorskip("pandas")


@pytest.fixture()
def v2(tmp_path):
    pd.DataFrame({"gid": ["g1", "g2", "g3"], "center_lat": [37.40, 37.41, 37.42],
                  "center_lon": [127.10, 127.11, 127.12]}).to_csv(tmp_path / "01_grid_cell.csv", index=False)
    pd.DataFrame({"complaint_id": ["c1", "c2", "c3", "c4"], "gid": ["g1", "g1", "g2", None],
                  "coord_accuracy": ["원본 좌표", "낮음", "보통", None], "dup_flag": [None] * 4, "relevance": [None] * 4,
                  "location_text": ["a", "b", "c", "d"], "report_type_raw": ["x"] * 4, "received_date": ["2026-01-01"] * 4,
                  "occurred_at": [None] * 4, "source_type": ["안전신문고(SPP)"] * 4}).to_csv(tmp_path / "79_src_complaint.csv", index=False)
    from app.services.grid import source as S
    S.use_csv(tmp_path)
    yield S
    S.use_csv(None)


def test_source_reads_csv(v2):
    assert v2.tables() == ["grid_cell", "src_complaint"]
    assert v2.columns("grid_cell")[0] == "gid"
    assert len(v2.read("src_complaint", usecols=["complaint_id"])) == 4


def test_c07_counts_low_both_ways(v2):
    from scripts import grid_complaint_count as c07
    out = c07.count(c07.load(None)).set_index("gid")
    assert out.loc["g1", "complaint_cnt"] == 2 and out.loc["g1", "complaint_cnt_excl_low"] == 1   # '낮음'은 포함·제외 둘 다 (ISS-033)
    assert out.loc["g3", "complaint_cnt"] == 0                                                   # 민원 없는 칸 = 0


def test_issue_format_columns():
    from app.services.quality.issue_format import COLUMNS, to_issue
    df = pd.DataFrame({"표": ["src_complaint"], "행 키": ["c1"], "검사": ["성남 격자 밖"], "값": ["37.2,127.0"], "비고": [""]})
    out = to_issue(df, "A-06", {"src_complaint": "complaint_id"})
    assert list(out.columns) == COLUMNS and out.loc[0, "error_code"] == "A06_OUT_OF_GRID"
    assert out.loc[0, "행 키"] == "complaint_id=c1"


def test_a08_same_content_rows():
    from scripts import quality_same_facility as a08
    d = pd.DataFrame({"row_id": [1, 2, 3], "seq_no": [1, 2, 3], "install_place": ["코끼리시장 앞"] * 2 + ["다른 곳"],
                      "lat": [37.37, 37.37, 37.40], "lon": [127.12, 127.12, 127.15]})
    got = a08.groups_in("src_hump_crosswalk", d, "row_id")
    assert [(k, t, rep) for k, t, rep, *_ in got] == [(2, "① 내용이 같은 행", 1)]
