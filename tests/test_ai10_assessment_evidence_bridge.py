from __future__ import annotations

import importlib
import importlib.util
import types
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1] / "app/services/AI-10"


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, BASE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bridge = load_module("bridge_test", "ai10_assessment_evidence_bridge.py")
provenance = load_module("provenance_test", "ai10_source_provenance.py")


@pytest.fixture(autouse=True)
def stub_bridge_provenance(monkeypatch):
    # bridge.importlib만 임시 대체한다. 전역 importlib.import_module은 변경하지 않는다.
    def load_provenance(name, package=None):
        if name == "app.services.AI-10.ai10_source_provenance":
            return provenance
        return importlib.import_module(name, package=package)

    monkeypatch.setattr(
        bridge,
        "importlib",
        types.SimpleNamespace(import_module=load_provenance),
    )


def args():
    return dict(
        table="assess_sidewalk",
        row={"width_under2_shape": "Y", "center_lat": 37.4},
        field="width_under2_shape",
        record_key="UFID=100",
        source_id="SRC18",
        evidence_state="estimated_or_derived",
        source_rows=[{"source_id": "SRC18", "access_level": "공개"}],
        source_confirmation="documented_column_source_ref",
    )


def test_explicit_reference_kept_without_raw_value():
    result = bridge.build_assessment_evidence(**args())
    assert result["evidence"]["source_id"] == "SRC18"
    assert "raw_value" not in result["evidence"]
    assert "37.4" not in str(result)
    assert result["external_transfer_approved"] is False


def test_reject_no_provenance():
    parameters = args()
    parameters["source_confirmation"] = ""
    with pytest.raises(ValueError):
        bridge.build_assessment_evidence(**parameters)


def test_reject_absent_src():
    parameters = args()
    parameters["source_id"] = "SRC999"
    with pytest.raises(ValueError):
        bridge.build_assessment_evidence(**parameters)


def test_reject_unknown_column():
    parameters = args()
    parameters["field"] = "unknown"
    with pytest.raises(ValueError):
        bridge.build_assessment_evidence(**parameters)
