import json
import pytest
from app import FINANCIAL_DATA, get_financial_summary, get_payment_history, check_scholarship_eligibility


def test_financial_data_has_three_students():
    assert len(FINANCIAL_DATA) == 3
    assert "WGU_2024_00142" in FINANCIAL_DATA
    assert "WGU_2024_00387" in FINANCIAL_DATA
    assert "WGU_2025_00051" in FINANCIAL_DATA


def test_get_financial_summary_known_student():
    result = json.loads(get_financial_summary("WGU_2024_00142"))
    assert result["student_id"] == "WGU_2024_00142"
    assert result["tuition_balance"] == 4280.00
    assert result["scholarship"]["name"] == "Dean's Merit Scholarship"
    assert result["financial_aid"]["name"] == "Federal Pell Grant"
    assert result["next_payment_due"] == "2026-05-01"


def test_get_financial_summary_unknown_student():
    result = json.loads(get_financial_summary("UNKNOWN"))
    assert "error" in result
    assert "not found" in result["error"]


def test_get_payment_history_known_student():
    result = json.loads(get_payment_history("WGU_2024_00142"))
    assert result["student_id"] == "WGU_2024_00142"
    assert len(result["payments"]) == 3
    assert result["payments"][0]["method"] == "ACH"
    assert result["payments"][0]["status"] == "completed"


def test_get_payment_history_unknown_student():
    result = json.loads(get_payment_history("UNKNOWN"))
    assert "error" in result


def test_check_scholarship_eligibility_known_student():
    result = json.loads(check_scholarship_eligibility("WGU_2024_00142"))
    assert result["student_id"] == "WGU_2024_00142"
    assert len(result["eligible_scholarships"]) == 2
    assert any(s["name"] == "STEM Excellence Award" for s in result["eligible_scholarships"])


def test_check_scholarship_eligibility_no_current_scholarship():
    result = json.loads(check_scholarship_eligibility("WGU_2025_00051"))
    assert result["current_scholarship"] is None
    assert len(result["eligible_scholarships"]) == 1


def test_student_ids_use_underscores():
    """Student IDs must use underscores, not dashes — dashes trigger SSN guardrail."""
    for sid in FINANCIAL_DATA:
        assert "_" in sid
        assert "-" not in sid
