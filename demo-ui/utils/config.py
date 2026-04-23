"""
Centralized configuration from environment variables.
All branding, service URLs, and demo data are configurable.
"""

import os
import json

# --- Branding ---
ORG_NAME = os.environ.get("ORG_NAME", "Western Governors University (WGU)")
ORG_SHORT = os.environ.get("ORG_SHORT", "WGU")
APP_TITLE = os.environ.get("APP_TITLE", f"{ORG_SHORT} Enrollment Advisor")
ADVISOR_ROLE = os.environ.get("ADVISOR_ROLE", "enrollment advisor")

# --- Service URLs ---
DATA_PRODUCT_URL = os.environ.get(
    "DATA_PRODUCT_URL", "http://data-product-api.wgu-demo.svc.cluster.local:8080"
)
GRAPH_DB_URL = os.environ.get(
    "GRAPH_DB_URL", "http://graph-db-mock.wgu-demo.svc.cluster.local:8081"
)
MCP_URL = os.environ.get(
    "MCP_URL", "http://agentgateway-proxy.agentgateway-system.svc.cluster.local:8080/financial-aid-mcp"
)

# --- Namespaces ---
NS_BACKEND = os.environ.get("NS_BACKEND", "wgu-demo")
NS_FRONTEND = os.environ.get("NS_FRONTEND", "wgu-demo-frontend")

# --- Demo students ---
# Override via STUDENTS_JSON env var: '[{"id":"S001","label":"John — CS"}]'
_DEFAULT_STUDENTS = [
    {"id": "WGU_2024_00142", "label": "Jordan Rivera — BS Computer Science"},
    {"id": "WGU_2024_00387", "label": "Priya Patel — BS Data Analytics"},
    {"id": "WGU_2025_00051", "label": "Marcus Chen — BS Cybersecurity and Information Assurance"},
]

_students_raw = os.environ.get("STUDENTS_JSON", "")
if _students_raw:
    _students_list = json.loads(_students_raw)
else:
    _students_list = _DEFAULT_STUDENTS

STUDENTS = {s["id"]: s["label"] for s in _students_list}
DEFAULT_STUDENT_ID = list(STUDENTS.keys())[0]

# --- System prompt ---
SYSTEM_PROMPT_TEMPLATE = os.environ.get("SYSTEM_PROMPT", f"""\
You are a helpful {ADVISOR_ROLE} for {ORG_NAME}. \
You help students understand their academic progress, remaining courses, program requirements, \
and financial situation.

When a student asks about their courses, progress, or enrollment, use the get_student_data tool \
to look up their information. The current student ID is {{student_id}}.

When a student asks about tuition, financial aid, scholarships, payments, or billing, \
use the financial aid tools (get_financial_summary, get_payment_history, check_scholarship_eligibility). \
The current student ID is {{student_id}}.

When a student asks a complex question involving both academic and financial information, \
use both sets of tools to provide a comprehensive answer.

Be friendly, professional, and specific. Reference actual course codes and names when discussing progress. \
If the student asks about courses they need to complete, calculate remaining courses from the data.""")


def system_prompt(student_id: str) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(student_id=student_id)
