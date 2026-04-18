import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app import app


client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


@patch("app.GRAPH_DB_URL", "http://mock-graph:8081")
@patch("app.requests.post")
def test_get_student(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "student_id": "WGU_2024_00142",
        "name": "Jordan Rivera",
        "program": "BS Computer Science",
        "enrollment_status": "active",
        "term": "April 2026",
        "gpa": 3.42,
        "competency_units_earned": 89,
        "competency_units_remaining": 32,
        "courses": [],
    }
    mock_post.return_value = mock_resp

    resp = client.get("/students/WGU_2024_00142")
    assert resp.status_code == 200
    data = resp.json()
    assert data["student_id"] == "WGU_2024_00142"
    assert data["program"] == "BS Computer Science"


@patch("app.GRAPH_DB_URL", "http://mock-graph:8081")
@patch("app.requests.post")
def test_get_student_not_found(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.json.return_value = {"detail": "Student UNKNOWN not found"}
    mock_post.return_value = mock_resp

    resp = client.get("/students/UNKNOWN")
    assert resp.status_code == 404


@patch("app.GRAPH_DB_URL", "http://mock-graph:8081")
@patch("app.requests.post")
def test_get_student_courses(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "student_id": "WGU_2024_00142",
        "name": "Jordan Rivera",
        "program": "BS Computer Science",
        "enrollment_status": "active",
        "term": "April 2026",
        "gpa": 3.42,
        "competency_units_earned": 89,
        "competency_units_remaining": 32,
        "courses": [
            {"code": "C949", "name": "Data Structures and Algorithms I", "status": "completed", "grade": "A-"},
            {"code": "C950", "name": "Data Structures and Algorithms II", "status": "in_progress", "grade": None},
        ],
    }
    mock_post.return_value = mock_resp

    resp = client.get("/students/WGU_2024_00142/courses")
    assert resp.status_code == 200
    data = resp.json()
    assert "completed" in data
    assert "in_progress" in data
    assert "not_started" in data
