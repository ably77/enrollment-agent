"""
Financial Aid MCP Server
Serves financial aid data via MCP protocol (StreamableHTTP).
"""

import json
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Financial Aid Service", host="0.0.0.0", port=8082)

FINANCIAL_DATA = {
    "WGU_2024_00142": {
        "student_id": "WGU_2024_00142",
        "name": "Jordan Rivera",
        "tuition_balance": 4280.00,
        "tuition_per_term": 4150.00,
        "scholarship": {
            "name": "Dean's Merit Scholarship",
            "amount_per_term": 2000.00,
            "type": "merit",
            "status": "active",
        },
        "financial_aid": {
            "name": "Federal Pell Grant",
            "amount_per_term": 3298.00,
            "type": "federal_grant",
            "status": "active",
        },
        "payment_plan": {
            "type": "monthly",
            "installments": 4,
            "amount_per_installment": 1070.00,
        },
        "next_payment_due": "2026-05-01",
        "payment_history": [
            {"date": "2026-04-01", "amount": 1070.00, "method": "ACH", "status": "completed"},
            {"date": "2026-03-01", "amount": 1070.00, "method": "ACH", "status": "completed"},
            {"date": "2026-02-01", "amount": 1070.00, "method": "credit_card", "status": "completed"},
        ],
        "eligible_scholarships": [
            {"name": "Dean's Merit Scholarship", "amount_per_term": 2000.00, "gpa_minimum": 3.25, "criteria": "GPA >= 3.25 in any program"},
            {"name": "STEM Excellence Award", "amount_per_term": 1500.00, "gpa_minimum": 3.5, "criteria": "GPA >= 3.5 in CS, Data Analytics, or Cybersecurity"},
        ],
    },
    "WGU_2024_00387": {
        "student_id": "WGU_2024_00387",
        "name": "Priya Patel",
        "tuition_balance": 2140.00,
        "tuition_per_term": 4150.00,
        "scholarship": {
            "name": "STEM Excellence Award",
            "amount_per_term": 1500.00,
            "type": "merit",
            "status": "active",
        },
        "financial_aid": {
            "name": "Federal Pell Grant",
            "amount_per_term": 3298.00,
            "type": "federal_grant",
            "status": "active",
        },
        "payment_plan": {
            "type": "per_term",
            "installments": 1,
            "amount_per_installment": 2140.00,
        },
        "next_payment_due": "2026-05-15",
        "payment_history": [
            {"date": "2026-01-15", "amount": 4150.00, "method": "ACH", "status": "completed"},
            {"date": "2025-07-15", "amount": 4150.00, "method": "ACH", "status": "completed"},
        ],
        "eligible_scholarships": [
            {"name": "Dean's Merit Scholarship", "amount_per_term": 2000.00, "gpa_minimum": 3.25, "criteria": "GPA >= 3.25 in any program"},
            {"name": "STEM Excellence Award", "amount_per_term": 1500.00, "gpa_minimum": 3.5, "criteria": "GPA >= 3.5 in CS, Data Analytics, or Cybersecurity"},
            {"name": "Near-Completion Bonus", "amount_per_term": 750.00, "gpa_minimum": 3.0, "criteria": "GPA >= 3.0 and fewer than 20 competency units remaining"},
        ],
    },
    "WGU_2025_00051": {
        "student_id": "WGU_2025_00051",
        "name": "Marcus Chen",
        "tuition_balance": 6220.00,
        "tuition_per_term": 4150.00,
        "scholarship": None,
        "financial_aid": {
            "name": "Federal Direct Unsubsidized Loan",
            "amount_per_term": 3500.00,
            "type": "federal_loan",
            "status": "active",
        },
        "payment_plan": {
            "type": "monthly",
            "installments": 6,
            "amount_per_installment": 1036.67,
        },
        "next_payment_due": "2026-05-01",
        "payment_history": [
            {"date": "2026-04-01", "amount": 1036.67, "method": "ACH", "status": "completed"},
            {"date": "2026-03-01", "amount": 1036.67, "method": "ACH", "status": "completed"},
        ],
        "eligible_scholarships": [
            {"name": "Dean's Merit Scholarship", "amount_per_term": 2000.00, "gpa_minimum": 3.25, "criteria": "GPA >= 3.25 in any program"},
        ],
    },
}


@mcp.tool()
def get_financial_summary(student_id: str) -> str:
    """Get financial summary for a student including tuition balance, scholarships, financial aid, and payment plan."""
    student = FINANCIAL_DATA.get(student_id)
    if not student:
        return json.dumps({"error": f"Student {student_id} not found"})
    summary = {
        "student_id": student["student_id"],
        "name": student["name"],
        "tuition_balance": student["tuition_balance"],
        "tuition_per_term": student["tuition_per_term"],
        "scholarship": student["scholarship"],
        "financial_aid": student["financial_aid"],
        "payment_plan": student["payment_plan"],
        "next_payment_due": student["next_payment_due"],
    }
    return json.dumps(summary)


@mcp.tool()
def get_payment_history(student_id: str) -> str:
    """Get payment history for a student including dates, amounts, methods, and status."""
    student = FINANCIAL_DATA.get(student_id)
    if not student:
        return json.dumps({"error": f"Student {student_id} not found"})
    return json.dumps({
        "student_id": student["student_id"],
        "name": student["name"],
        "payments": student["payment_history"],
    })


@mcp.tool()
def check_scholarship_eligibility(student_id: str) -> str:
    """Check which scholarships a student is eligible for based on their GPA and program. Useful when combined with academic data to advise students on financial options."""
    student = FINANCIAL_DATA.get(student_id)
    if not student:
        return json.dumps({"error": f"Student {student_id} not found"})
    return json.dumps({
        "student_id": student["student_id"],
        "name": student["name"],
        "current_scholarship": student["scholarship"],
        "eligible_scholarships": student["eligible_scholarships"],
    })


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
