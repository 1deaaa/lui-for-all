import asyncio
import os
import sys
import uuid

# 把 backend 目录加入 python path
sys.path.insert(0, r"d:\Desktop\lui-for-all\backend")

from app.schemas.task import ExecutionArtifact

def test_pydantic():
    artifact_data = {
        "artifact_id": str(uuid.uuid4()),
        "step_id": str(uuid.uuid4()),
        "route_id": "GET /api/test",
        "method": "GET",
        "url": "http://localhost:8000/api/test",
        "request_body": {},  # parameters
        "status_code": 200,
        "response_body": {"test": "ok"},
        "duration_ms": 150,
        "redacted": False,
        "error": None,
    }
    try:
        art = ExecutionArtifact(**artifact_data)
        print("Success!", art)
    except Exception as e:
        print("Failed!")
        print(e)

if __name__ == "__main__":
    test_pydantic()
