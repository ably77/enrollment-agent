from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Graph DB Mock (Neptune Simulator)")

STUDENTS = {
    "WGU_2024_00142": {
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
            {"code": "C951", "name": "Introduction to Artificial Intelligence", "status": "not_started", "grade": None},
            {"code": "C952", "name": "Computer Architecture", "status": "completed", "grade": "B+"},
            {"code": "C191", "name": "Operating Systems for Programmers", "status": "completed", "grade": "A"},
            {"code": "C482", "name": "Software I", "status": "completed", "grade": "B"},
            {"code": "C195", "name": "Software II - Advanced Java Concepts", "status": "completed", "grade": "B+"},
            {"code": "D287", "name": "Java Frameworks", "status": "completed", "grade": "A-"},
            {"code": "C868", "name": "Software Engineering Capstone", "status": "not_started", "grade": None},
            {"code": "D370", "name": "IT Leadership Foundations", "status": "not_started", "grade": None},
            {"code": "C960", "name": "Discrete Mathematics II", "status": "in_progress", "grade": None},
        ],
    },
    "WGU_2024_00387": {
        "student_id": "WGU_2024_00387",
        "name": "Priya Patel",
        "program": "BS Data Analytics",
        "enrollment_status": "active",
        "term": "April 2026",
        "gpa": 3.78,
        "competency_units_earned": 104,
        "competency_units_remaining": 17,
        "courses": [
            {"code": "D204", "name": "The Data Analytics Journey", "status": "completed", "grade": "A"},
            {"code": "D205", "name": "Data Acquisition", "status": "completed", "grade": "A-"},
            {"code": "D206", "name": "Data Cleaning", "status": "completed", "grade": "A"},
            {"code": "D207", "name": "Exploratory Data Analysis", "status": "completed", "grade": "B+"},
            {"code": "D208", "name": "Predictive Modeling", "status": "in_progress", "grade": None},
            {"code": "D209", "name": "Data Mining I", "status": "not_started", "grade": None},
            {"code": "D210", "name": "Representation and Reporting", "status": "not_started", "grade": None},
            {"code": "D211", "name": "Advanced Data Acquisition", "status": "not_started", "grade": None},
            {"code": "D212", "name": "Data Mining II", "status": "not_started", "grade": None},
            {"code": "D213", "name": "Advanced Data Analytics", "status": "not_started", "grade": None},
            {"code": "D214", "name": "Data Analytics Graduate Capstone", "status": "not_started", "grade": None},
        ],
    },
    "WGU_2025_00051": {
        "student_id": "WGU_2025_00051",
        "name": "Marcus Chen",
        "program": "BS Cybersecurity and Information Assurance",
        "enrollment_status": "active",
        "term": "April 2026",
        "gpa": 3.15,
        "competency_units_earned": 45,
        "competency_units_remaining": 76,
        "courses": [
            {"code": "C172", "name": "Network and Security Foundations", "status": "completed", "grade": "B+"},
            {"code": "C173", "name": "Scripting and Programming Foundations", "status": "completed", "grade": "B"},
            {"code": "C836", "name": "Fundamentals of Information Security", "status": "completed", "grade": "A-"},
            {"code": "C844", "name": "Emerging Technologies in Cybersecurity", "status": "completed", "grade": "B+"},
            {"code": "C840", "name": "Digital Forensics in Cybersecurity", "status": "in_progress", "grade": None},
            {"code": "C841", "name": "Legal Issues in Information Security", "status": "in_progress", "grade": None},
            {"code": "C842", "name": "Cyber Defense and Countermeasures", "status": "not_started", "grade": None},
            {"code": "C843", "name": "Managing Information Security", "status": "not_started", "grade": None},
            {"code": "D153", "name": "Penetration Testing and Vulnerability Analysis", "status": "not_started", "grade": None},
            {"code": "D430", "name": "Fundamentals of Zero Trust Security", "status": "not_started", "grade": None},
            {"code": "C769", "name": "IT Capstone Written Project", "status": "not_started", "grade": None},
        ],
    },
}


class QueryRequest(BaseModel):
    query: str
    student_id: str


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/query")
def query(req: QueryRequest):
    student = STUDENTS.get(req.student_id)
    if not student:
        raise HTTPException(status_code=404, detail=f"Student {req.student_id} not found")
    return student


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
