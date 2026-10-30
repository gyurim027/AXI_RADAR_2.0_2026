from importlib import import_module

models = import_module("app.services.AI-10.ai10_case_draft")
CaseInput = models.CaseInput
EvidenceItem = models.EvidenceItem


def sidewalk_width_to_case(row: dict) -> CaseInput:
    if not isinstance(row, dict):
        raise ValueError("Invalid sidewalk record")

    ufid = str(row.get("UFID") or "").strip()
    if not ufid:
        raise ValueError("Sidewalk UFID is required")

    width = row.get("width_m_raw")
    status = row.get("width_status")
    method = row.get("measure_method")
    under2 = row.get("width_under2_raw")
    mismatch = row.get("width2_mismatch")

    missing_method = (
        method is None
        or str(method).strip() == ""
        or str(method).strip() == "\uc6d0\ubcf8\uc5d0 \uc5c6\uc74c"
    )

    items = []
    for column, value in (
        ("width_m_raw", width),
        ("width_status", status),
        ("measure_method", method),
        ("width_under2_raw", under2),
        ("width2_mismatch", mismatch),
    ):
        state = "missing" if (
            value is None or (column == "measure_method" and missing_method)
        ) else "estimated_or_derived"

        items.append(EvidenceItem(
            source_table="assess_sidewalk",
            source_id=None,
            source_column=column,
            record_reference=f"assess_sidewalk:UFID:{ufid}",
            raw_value=value,
            claim_or_finding=f"Source column {column}",
            evidence_state=state,
        ))

    if mismatch == "Y":
        issue = (
            "\uc6d0\ubcf8 \ubcf4\ub3c4 \ud3ed\uacfc \ub3c4\ud615 "
            "\uae30\uc900\uc758 2.0m \ubbf8\ub9cc \ud310\uc815\uc774 "
            "\uc11c\ub85c \ub2e4\ub985\ub2c8\ub2e4. "
            "\ud604\uc7a5 \uc720\ud6a8\ud3ed\uc740 \ud655\uc778\ub418\uc9c0 "
            "\uc54a\uc558\uc2b5\ub2c8\ub2e4."
        )
    elif under2 == "Y":
        issue = (
            f"\uc6d0\ubcf8 \ub3c4\uba74\uc758 \ubcf4\ub3c4 \ud3ed\uc740 "
            f"{width}m\uc774\uba70 2.0m \ubbf8\ub9cc\uc73c\ub85c "
            "\ud45c\uc2dc\ub418\uc5b4 \uc788\uc2b5\ub2c8\ub2e4. "
            "\ud604\uc7a5 \uc720\ud6a8\ud3ed\uc740 \ubbf8\ud655\uc778\uc785\ub2c8\ub2e4."
        )
    else:
        issue = (
            f"\uc6d0\ubcf8 \ub3c4\uba74\uc758 \ubcf4\ub3c4 \ud3ed\uc740 "
            f"{width}m\ub85c \uae30\ub85d\ub418\uc5b4 \uc788\uc2b5\ub2c8\ub2e4. "
            "\ud604\uc7a5 \uc720\ud6a8\ud3ed\uc740 \ubbf8\ud655\uc778\uc785\ub2c8\ub2e4."
        )

    return CaseInput(
        case_reference=f"assess_sidewalk:{ufid}:width",
        issue_description=issue,
        evidence_items=items,
        facility_type="sidewalk",
        problem_type_text="sidewalk width verification",
        gid=row.get("gid"),
        facility_id=ufid,
        assessment=str(under2) if under2 is not None else None,
        ck_reference=None,
    )
