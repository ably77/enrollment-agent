import os
import requests
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Student Data Product API")

GRAPH_DB_URL = os.environ.get("GRAPH_DB_URL", "http://graph-db-mock:8081")


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/students/{student_id}")
def get_student(student_id: str):
    """Fetch student academic data from the graph database."""
    resp = requests.post(
        f"{GRAPH_DB_URL}/query",
        json={"query": f"MATCH (s:Student {{id: '{student_id}'}})", "student_id": student_id},
        timeout=10,
    )
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")
    resp.raise_for_status()
    return resp.json()


@app.get("/students/{student_id}/courses")
def get_student_courses(student_id: str):
    """Fetch student courses grouped by status."""
    resp = requests.post(
        f"{GRAPH_DB_URL}/query",
        json={"query": f"MATCH (s:Student)-[:ENROLLED]->(c:Course)", "student_id": student_id},
        timeout=10,
    )
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")
    resp.raise_for_status()

    data = resp.json()
    courses = data.get("courses", [])
    return {
        "student_id": student_id,
        "program": data.get("program"),
        "completed": [c for c in courses if c["status"] == "completed"],
        "in_progress": [c for c in courses if c["status"] == "in_progress"],
        "not_started": [c for c in courses if c["status"] == "not_started"],
        "total_completed": len([c for c in courses if c["status"] == "completed"]),
        "total_remaining": len([c for c in courses if c["status"] != "completed"]),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
