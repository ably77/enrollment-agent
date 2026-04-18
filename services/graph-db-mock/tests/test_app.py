import pytest
from fastapi.testclient import TestClient
from app import app


client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


def test_query_student_enrollment():
    resp = client.post("/query", json={
        "query": "MATCH (s:Student {id: 'WGU_2024_00142'})-[:ENROLLED_IN]->(p:Program) RETURN s, p",
        "student_id": "WGU_2024_00142",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["student_id"] == "WGU_2024_00142"
    assert "program" in data
    assert "courses" in data
    assert len(data["courses"]) > 0


def test_query_unknown_student():
    resp = client.post("/query", json={
        "query": "MATCH (s:Student {id: 'UNKNOWN'})",
        "student_id": "UNKNOWN",
    })
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_query_student_courses():
    resp = client.post("/query", json={
        "query": "MATCH (s:Student)-[:COMPLETED]->(c:Course)",
        "student_id": "WGU_2024_00142",
    })
    assert resp.status_code == 200
    data = resp.json()
    completed = [c for c in data["courses"] if c["status"] == "completed"]
    assert len(completed) > 0
    assert all("grade" in c for c in completed)
