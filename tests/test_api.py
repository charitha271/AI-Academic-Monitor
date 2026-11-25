"""API Test Suite for Flask Application Routes."""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.app import app


def run_api_tests():
    print("=" * 60)
    print("PHASE 3: FLASK API ROUTE VERIFICATION SUITE")
    print("=" * 60)

    client = app.test_client()

    # 1. Test GET / and GET /parent
    res_root = client.get("/")
    assert res_root.status_code == 302, f"GET / expected 302 redirect, got {res_root.status_code}"
    res_parent = client.get("/parent")
    assert res_parent.status_code == 200, f"GET /parent expected 200, got {res_parent.status_code}"
    print("[PASS] GET / -> 302 Redirect & GET /parent -> 200 OK (Dashboard template rendered)")

    # 2. Test GET /api/health
    res = client.get("/api/health")
    assert res.status_code == 200, f"GET /api/health expected 200, got {res.status_code}"
    data = res.get_json()
    assert data == {"status": "ok"}, f"Expected status ok, got {data}"
    print("[PASS] GET /api/health -> HTTP 200 (status: ok)")

    # 3. Test GET /api/students
    res = client.get("/api/students")
    assert res.status_code == 200, f"GET /api/students expected 200, got {res.status_code}"
    data = res.get_json()
    assert "students" in data
    assert len(data["students"]) == 500, f"Expected 500 students, got {len(data['students'])}"
    print(f"[PASS] GET /api/students -> HTTP 200 ({len(data['students'])} students returned)")

    # 4. Test Sample Students
    sample_students = ["STU-0004", "STU-0001", "STU-0185"]

    for sid in sample_students:
        print("\n" + "-" * 50)
        print(f"Testing Endpoints for Student: {sid}")
        print("-" * 50)

        # GET /api/student/<id> (Complete Dashboard)
        res = client.get(f"/api/student/{sid}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        dash = res.get_json()
        assert dash["metadata"]["student_id"] == sid
        assert "profile" in dash
        assert "prediction" in dash
        assert "topics" in dash
        assert "recommendations" in dash
        assert "explanation" in dash
        print(f"  [PASS] GET /api/student/{sid} -> HTTP 200")
        print(f"         Prediction: {dash['prediction']['predicted_difficulty']} ({dash['prediction']['status_badge']})")
        print(f"         Confidence: {dash['prediction']['confidence_percentage']}%")
        print(f"         Topics count: {len(dash['topics'])}")
        print(f"         Recommendations count: {len(dash['recommendations']['topics_needing_attention'])}")

        # GET /api/student/<id>/prediction
        res = client.get(f"/api/student/{sid}/prediction")
        assert res.status_code == 200
        pred = res.get_json()
        assert "predicted_difficulty" in pred
        assert "confidence_percentage" in pred
        assert "probabilities" in pred
        print(f"  [PASS] GET /api/student/{sid}/prediction -> HTTP 200")

        # GET /api/student/<id>/topics
        res = client.get(f"/api/student/{sid}/topics")
        assert res.status_code == 200
        topics = res.get_json()
        assert isinstance(topics, list)
        assert len(topics) == 25
        print(f"  [PASS] GET /api/student/{sid}/topics -> HTTP 200 ({len(topics)} topics)")

        # GET /api/student/<id>/recommendations
        res = client.get(f"/api/student/{sid}/recommendations")
        assert res.status_code == 200
        recs = res.get_json()
        assert "topics_needing_attention" in recs
        assert "parental_guidance" in recs
        print(f"  [PASS] GET /api/student/{sid}/recommendations -> HTTP 200")

        # GET /api/student/<id>/explanation
        res = client.get(f"/api/student/{sid}/explanation")
        assert res.status_code == 200
        exp = res.get_json()
        assert "top_contributing_factors" in exp
        assert "narrative_explanations" in exp
        print(f"  [PASS] GET /api/student/{sid}/explanation -> HTTP 200")

    # 5. Test 404 for Unknown Student ID
    print("\n" + "-" * 50)
    print("Testing 404 Error Handling for Unknown Student ID:")
    print("-" * 50)

    unknown_endpoints = [
        "/api/student/STU-9999",
        "/api/student/STU-9999/prediction",
        "/api/student/STU-9999/topics",
        "/api/student/STU-9999/recommendations",
        "/api/student/STU-9999/explanation",
    ]

    for ep in unknown_endpoints:
        res = client.get(ep)
        assert res.status_code == 404, f"Expected 404 for {ep}, got {res.status_code}"
        data = res.get_json()
        assert data == {"error": "Student ID not found"}, f"Expected error JSON, got {data}"
        print(f"  [PASS] GET {ep} -> HTTP 404 {data}")

    print("\n" + "=" * 60)
    print("ALL API TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_api_tests()
