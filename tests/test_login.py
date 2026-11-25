"""Automated verification test for Phase 1: Unified Login Page and Role Flow."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.app import app


def run_login_tests():
    print("=" * 65)
    print("PHASE 1 VERIFICATION: UNIFIED LOGIN PAGE & ROLE AUTHENTICATION")
    print("=" * 65)

    client = app.test_client()

    # 1. Test GET / redirects to /login
    res = client.get("/")
    assert res.status_code == 302, f"GET / expected 302 redirect, got {res.status_code}"
    assert "/login" in res.headers["Location"], f"Expected redirect to /login, got {res.headers['Location']}"
    print("[PASS] GET / -> 302 Redirect to /login")

    # 2. Test GET /login renders login page
    res = client.get("/login")
    assert res.status_code == 200, f"GET /login expected 200, got {res.status_code}"
    html = res.get_data(as_text=True)
    assert "AI Academic Monitor" in html
    assert "Parent" in html
    assert "Student" in html
    assert "Explainable AI-Based Student Progress Prediction &amp; Personalized Learning Support" in html
    assert "brand-description" not in html
    assert "brand-feature-list" not in html
    assert "brand-visual" not in html
    assert "student_study_art.svg" not in html
    assert "Welcome back" in html
    assert "Academic Monitoring" in html
    assert "Personal Learning Portal" in html
    assert 'id="parentRoleBtn"' in html and 'aria-pressed="true"' in html
    assert 'id="studentRoleBtn"' in html and 'aria-pressed="false"' in html
    assert "Student ID" in html
    print("[PASS] GET /login -> 200 OK (Rendered unified login page with roles and branding)")

    # 3. Test Successful Parent Login (JSON POST)
    res = client.post("/login", json={
        "role": "parent",
        "student_id": "STU-0004",
        "password": "parent123"
    })
    assert res.status_code == 200, f"Parent login expected 200, got {res.status_code}"
    data = res.get_json()
    assert data["success"] is True
    assert data["role"] == "parent"
    assert data["student_id"] == "STU-0004"
    assert "/parent?student_id=STU-0004" in data["redirect_url"]
    print(f"[PASS] POST /login (Parent JSON) -> 200 OK | Redirect: {data['redirect_url']}")

    # 4. Test Successful Parent Login (Form POST)
    res = client.post("/login", data={
        "role": "parent",
        "student_id": "STU-0004",
        "password": "parent123"
    }, follow_redirects=False)
    assert res.status_code == 302, f"Parent form login expected 302, got {res.status_code}"
    assert "/parent?student_id=STU-0004" in res.headers["Location"]
    print(f"[PASS] POST /login (Parent Form) -> 302 Redirect: {res.headers['Location']}")

    # 5. Test Successful Student Login (JSON POST)
    res = client.post("/login", json={
        "role": "student",
        "student_id": "STU-0004",
        "password": "student123"
    })
    assert res.status_code == 200, f"Student login expected 200, got {res.status_code}"
    data = res.get_json()
    assert data["success"] is True
    assert data["role"] == "student"
    assert data["student_id"] == "STU-0004"
    assert "/student?student_id=STU-0004" in data["redirect_url"]
    print(f"[PASS] POST /login (Student JSON) -> 200 OK | Redirect: {data['redirect_url']}")

    # 6. Test Successful Student Login (Form POST)
    res = client.post("/login", data={
        "role": "student",
        "student_id": "STU-0004",
        "password": "student123"
    }, follow_redirects=False)
    assert res.status_code == 302, f"Student form login expected 302, got {res.status_code}"
    assert "/student?student_id=STU-0004" in res.headers["Location"]
    print(f"[PASS] POST /login (Student Form) -> 302 Redirect: {res.headers['Location']}")

    # 7. Test Invalid Credentials
    print("\nTesting Invalid Credential Cases:")

    # Case A: Wrong parent password
    res = client.post("/login", json={
        "role": "parent",
        "student_id": "STU-0004",
        "password": "wrongpassword"
    })
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    err = res.get_json()["error"]
    print(f"  [PASS] Wrong Parent password rejected -> HTTP 401: '{err}'")

    # Case B: Wrong student password
    res = client.post("/login", json={
        "role": "student",
        "student_id": "STU-0004",
        "password": "wrongpassword"
    })
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    err = res.get_json()["error"]
    print(f"  [PASS] Wrong Student password rejected -> HTTP 401: '{err}'")

    # Case C: Unknown student ID
    res = client.post("/login", json={
        "role": "parent",
        "student_id": "STU-9999",
        "password": "parent123"
    })
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    err = res.get_json()["error"]
    print(f"  [PASS] Unknown Student ID rejected -> HTTP 401: '{err}'")

    # Case D: Invalid role
    res = client.post("/login", json={
        "role": "admin",
        "student_id": "STU-0004",
        "password": "parent123"
    })
    assert res.status_code == 400, f"Expected 400, got {res.status_code}"
    err = res.get_json()["error"]
    print(f"  [PASS] Invalid role rejected -> HTTP 400: '{err}'")

    # 8. Test Target Dashboards Accessibility
    print("\nTesting Dashboard Targets Accessibility:")
    res_parent = client.get("/parent?student_id=STU-0004")
    assert res_parent.status_code == 200, f"Expected 200, got {res_parent.status_code}"
    assert "Parent Dashboard" in res_parent.get_data(as_text=True)
    print("  [PASS] GET /parent?student_id=STU-0004 -> HTTP 200 OK")

    res_student = client.get("/student?student_id=STU-0004")
    assert res_student.status_code == 200, f"Expected 200, got {res_student.status_code}"
    assert "Student Learning" in res_student.get_data(as_text=True)
    print("  [PASS] GET /student?student_id=STU-0004 -> HTTP 200 OK")

    # 9. Verify All Existing APIs Still Work
    print("\nTesting Existing Flask APIs:")
    res = client.get("/api/health")
    assert res.status_code == 200 and res.get_json() == {"status": "ok"}
    print("  [PASS] GET /api/health -> HTTP 200")

    res = client.get("/api/students")
    assert res.status_code == 200 and len(res.get_json()["students"]) == 500
    print("  [PASS] GET /api/students -> HTTP 200 (500 students)")

    for sid in ["STU-0004", "STU-0001", "STU-0185"]:
        res = client.get(f"/api/student/{sid}")
        assert res.status_code == 200
        dash = res.get_json()
        assert "prediction" in dash and "profile" in dash and "topics" in dash
        print(f"  [PASS] GET /api/student/{sid} -> HTTP 200 ({dash['prediction']['predicted_difficulty']})")

    print("\n" + "=" * 65)
    print("ALL PHASE 1 UNIFIED LOGIN TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == "__main__":
    run_login_tests()
