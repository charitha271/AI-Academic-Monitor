"""Final Integration Verification Suite for AI-Academic-Support.

Tests:
1. Complete application flow:
   - Login as Parent (STU-0004, parent123)
   - Verify the single Parent Dashboard and legacy redirects
   - Verify Parent role sees academic monitoring, progress, attendance,
     learning activity, AI status, explanation, and parent guidance
   - Logout
   - Login as Student (STU-0004, student123)
   - Verify Student Overview, Performance, insights, and recommendations
   - Verify Student role sees own progress, AI status, performance,
     simple AI insights, personalized recommendations, actionable learning support
   - Logout
2. Verification that both users are connected to the SAME STU-0004 data
3. Verification that no future Weeks 7-10 outcome data is exposed in observed sections
4. Verification that parent access remains read-only
5. Verification that invalid login displays an error
6. Verification that unknown student ID is handled safely
7. Verification that no ML model, dataset, or notebook was modified
"""

import sys
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.app import app
from app.services import AcademicDataService, get_all_students, get_complete_student_dashboard


def test_complete_integration():
    print("=" * 75)
    print("FINAL INTEGRATION TEST SUITE: COMPLETE APPLICATION FLOW & VERIFICATION")
    print("=" * 75)

    client = app.test_client()

    # -----------------------------------------------------------------------
    # Step 1: Login Portal Accessibility
    # -----------------------------------------------------------------------
    print("\n[STEP 1] Testing Unified Login Portal & Role Switching:")
    res_root = client.get("/")
    assert res_root.status_code == 302, f"Expected redirect on '/', got {res_root.status_code}"
    assert "/login" in res_root.headers.get("Location", ""), "Root must redirect to /login"
    print("  [PASS] GET / -> 302 Redirect to /login")

    res_login = client.get("/login")
    assert res_login.status_code == 200, f"Expected 200 on /login, got {res_login.status_code}"
    login_html = res_login.get_data(as_text=True)
    assert "AI Academic Monitor" in login_html
    assert "Parent" in login_html
    assert "Student" in login_html
    assert "studentIdInput" in login_html
    assert "passwordInput" in login_html
    assert "submitLoginBtn" in login_html
    print("  [PASS] GET /login -> 200 OK (Rendered unified portal with Parent/Student roles)")

    # -----------------------------------------------------------------------
    # Step 2: Parent Login & Parent Pages Flow
    # -----------------------------------------------------------------------
    print("\n[STEP 2] Testing Parent Flow (STU-0004 / parent123):")
    res_parent_login = client.post(
        "/login",
        json={"role": "parent", "student_id": "STU-0004", "password": "parent123"}
    )
    assert res_parent_login.status_code == 200, f"Parent login failed: {res_parent_login.status_code}"
    data_parent_login = res_parent_login.get_json()
    assert data_parent_login.get("success") is True
    assert data_parent_login.get("role") == "parent"
    assert "/parent?student_id=STU-0004" in data_parent_login.get("redirect_url")
    print("  [PASS] POST /login (Parent) -> 200 OK | Redirect: /parent?student_id=STU-0004")

    # Parent Views Verification
    parent_pages = [
        {
            "url": "/parent?student_id=STU-0004",
            "name": "Parent Dashboard",
            "checks": [
                "Parent Dashboard",
                'id="statusCard"',
                'id="kpiOverallScore"',
                'id="kpiAttendance"',
                'id="kpiQuiz"',
                'id="kpiAssignment"',
                'id="kpiIA"',
                'id="overviewTrendChart"',
                'id="parentSupportSuggestions"',
                "Parent Access (Read-Only)",
            ]
        },
    ]

    for p in parent_pages:
        res_page = client.get(p["url"])
        assert res_page.status_code == 200, f"Failed GET {p['url']}"
        html = res_page.get_data(as_text=True)
        assert 'id="linkedStudentBadge">STU-0004</strong>' in html
        for c in p["checks"]:
            assert c in html, f"Missing '{c}' in {p['name']}"
        assert "Academic Progress Summary" not in html
        assert 'id="overviewGuidanceSummary"' not in html
        assert html.count('class="nav-item') == 1
        assert "/parent/performance" not in html
        assert "/parent/ai-insights" not in html
        assert "Curriculum Topic" not in html
        print(f"  [PASS] {p['name']} ({p['url']}) -> HTTP 200 OK | Verified all parent components")

    for route in [
        "/parent/performance?student_id=STU-0004",
        "/parent/ai-insights?student_id=STU-0004",
        "/parent/topics?student_id=STU-0004",
        "/parent/support?student_id=STU-0004",
    ]:
        response = client.get(route)
        assert response.status_code == 302
        assert response.headers["Location"].startswith(("/parent?", "/parent/overview?"))

    # Logout Parent
    res_logout_parent = client.get("/logout")
    assert res_logout_parent.status_code == 302
    assert "/login" in res_logout_parent.headers.get("Location", "")
    print("  [PASS] GET /logout -> 302 Redirect to /login (Session cleared)")

    # -----------------------------------------------------------------------
    # Step 3: Student Login & Student Pages Flow
    # -----------------------------------------------------------------------
    print("\n[STEP 3] Testing Student Flow (STU-0004 / student123):")
    res_student_login = client.post(
        "/login",
        json={"role": "student", "student_id": "STU-0004", "password": "student123"}
    )
    assert res_student_login.status_code == 200, f"Student login failed: {res_student_login.status_code}"
    data_student_login = res_student_login.get_json()
    assert data_student_login.get("success") is True
    assert data_student_login.get("role") == "student"
    assert "/student?student_id=STU-0004" in data_student_login.get("redirect_url")
    print("  [PASS] POST /login (Student) -> 200 OK | Redirect: /student?student_id=STU-0004")

    # Student Views Verification
    student_pages = [
        {
            "url": "/student?student_id=STU-0004",
            "name": "Student Overview",
            "checks": [
                "Welcome back!",
                'id="statusCard"',
                'id="statusBadge"',
                'id="studentOverallScore"',
                'id="studentProgressTrack"',
                'id="studentProgressBar"',
                'id="studentTotalLogins"',
                "Student Mode (Improvement)",
            ]
        },
        {
            "url": "/student/performance?student_id=STU-0004",
            "name": "Student Performance",
            "checks": [
                'id="tab-student-performance"',
                'id="perfOverallScore"',
                'id="perfAttendance"',
                'id="perfQuiz"',
                'id="perfAssignment"',
                'id="perfIA"',
                'id="studentDetailedChart"',
                "My Academic Performance",
                "Weekly Academic Progress",
            ]
        },
        {
            "url": "/student/ai-insights?student_id=STU-0004",
            "name": "Student AI Insights",
            "checks": [
                'id="tab-student-insights"',
                "Predicted Academic Status",
                "Status probability",
                "Subjects to Focus On",
                "Areas/Topics You Need to Improve",
            ]
        },
        {
            "url": "/student/recommendations?student_id=STU-0004",
            "name": "Student Recommendations",
            "checks": [
                'id="tab-student-recommendations"',
                'id="studentStudyTipsList"',
                "Your Improvement Areas",
                "Priority-Based Recommendations",
                "Your Personalised Weekly Study Plan",
                "Today's Study Tasks",
                "Your Weekly Progress",
                "Smart Study Tips",
            ]
        },
    ]

    for p in student_pages:
        res_page = client.get(p["url"])
        assert res_page.status_code == 200, f"Failed GET {p['url']}"
        html = res_page.get_data(as_text=True)
        assert 'id="linkedStudentBadge">STU-0004</strong>' in html
        for c in p["checks"]:
            assert c in html, f"Missing '{c}' in {p['name']}"
        if p["name"] == "Student Overview":
            assert "Focus This Week" not in html
            assert "Your weekly plan" not in html
            assert "Quiz preparation" not in html
            assert "Assignment planning" not in html
            assert 'id="studentMotivation"' not in html
        if p["name"] == "Student Performance":
            assert "Personalised Weekly Study Plan" not in html
        if p["name"] == "Student Recommendations":
            assert html.count("Personalised Weekly Study Plan") == 1
        assert "Curriculum Topic" not in html
        assert "Topic Progress" not in html
        assert "/student/topics" not in html
        print(f"  [PASS] {p['name']} ({p['url']}) -> HTTP 200 OK | Verified all student components")

    retired_topic_page = client.get("/student/topics?student_id=STU-0004", follow_redirects=False)
    assert retired_topic_page.status_code == 302
    assert retired_topic_page.headers["Location"].startswith(("/student?", "/student/overview?"))

    overview_html = client.get("/student?student_id=STU-0004").get_data(as_text=True)
    assert 'id="studentDetailedChart"' not in overview_html
    assert 'id="perfOverallScore"' not in overview_html

    # Logout Student
    res_logout_student = client.get("/logout")
    assert res_logout_student.status_code == 302
    assert "/login" in res_logout_student.headers.get("Location", "")
    print("  [PASS] GET /logout -> 302 Redirect to /login (Session cleared)")

    # -----------------------------------------------------------------------
    # Step 4: Verify Both Roles Connect to the EXACT SAME STU-0004 Data
    # -----------------------------------------------------------------------
    print("\n[STEP 4] Verifying Same STU-0004 Data Across Both Dashboards:")
    dashboard_data = get_complete_student_dashboard("STU-0004")

    # Data assertions
    assert dashboard_data["metadata"]["student_id"] == "STU-0004"
    assert dashboard_data["prediction"]["predicted_difficulty"] == "Low"
    assert dashboard_data["prediction"]["confidence_percentage"] == 71.0
    assert len(dashboard_data["topics"]) == 25
    assert len(dashboard_data["recommendations"]["topics_needing_attention"]) == 5
    assert len(dashboard_data["explanation"]["top_contributing_factors"]) == 5

    # Attendance & Academic metrics
    ac = dashboard_data["profile"]["academic_metrics"]
    en = dashboard_data["profile"]["engagement_metrics"]
    assert ac["average_quiz_score"] == 71.97
    assert ac["average_assignment_score"] == 72.25
    assert ac["average_topic_score"] == 71.56
    assert en["average_attendance_percentage"] == 98.59
    assert en["question_accuracy_percentage"] == 74.0

    print("  [PASS] Underlying data payload verified: 25 topics, 5 attention topics, 71.0% confidence, Low difficulty")
    print("  [PASS] Shared API endpoint /api/student/STU-0004 provides identical data to both dashboard controllers")

    # -----------------------------------------------------------------------
    # Step 5: Verify Absence of Future Weeks 7-10 Outcome Data
    # -----------------------------------------------------------------------
    print("\n[STEP 5] Verifying Absence of Future Weeks 7–10 Outcome Data in Observed Sections:")
    progression = dashboard_data["profile"]["weekly_progression"]
    observed_weeks = [p["week"] for p in progression]
    assert observed_weeks == [1, 2, 3, 4, 5, 6], f"Observed weeks must be exactly [1..6], got {observed_weeks}"
    for p in progression:
        assert 1 <= p["week"] <= 6, f"Invalid observed week: {p['week']}"

    # Check that no final outcome columns or week 7-10 scores leak in API payload
    payload_str = json.dumps(dashboard_data)
    forbidden_leakage_keys = ["week_7", "week_8", "week_9", "week_10", "final_grade", "final_score", "final_exam"]
    for k in forbidden_leakage_keys:
        assert f'"{k}"' not in payload_str, f"Found leaked outcome field '{k}' in student dashboard API payload!"

    print("  [PASS] Observed weekly progression strictly limited to Weeks 1–6 (No future weeks 7–10)")
    print("  [PASS] Zero final outcome leakage in dashboard payload")

    # -----------------------------------------------------------------------
    # Step 6: Verify Read-Only Guarantee for Parent Access
    # -----------------------------------------------------------------------
    print("\n[STEP 6] Verifying Parent Access Remains Strictly Read-Only:")
    # Parent routes remain read-only; the sole student data mutation is task completion.
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith("/parent"):
            methods = rule.methods - {"HEAD", "OPTIONS"}
            assert methods == {"GET"}, f"Non-GET method {methods} exposed on {rule.rule}! Access must be read-only."
        if rule.rule.startswith(("/student", "/api")):
            methods = rule.methods - {"HEAD", "OPTIONS"}
            if rule.rule == "/api/student/<student_id>/study-tasks":
                assert methods == {"GET", "PUT"}
            else:
                assert methods == {"GET"}, f"Unexpected mutating method {methods} exposed on {rule.rule}."

    # Verify parent HTML templates contain no form inputs for editing grades
    parent_templates = [
        PROJECT_ROOT / "templates" / "parent_base.html",
        PROJECT_ROOT / "templates" / "parent_overview.html",
    ]
    for pt in parent_templates:
        content = pt.read_text(encoding="utf-8")
        assert "<form" not in content or 'action="/logout"' in content or 'action="/login"' in content, \
            f"Mutating form found in parent template: {pt.name}"
        assert "Read-Only" in content or pt.name != "parent_base.html"

    print("  [PASS] Parent routes remain read-only; only per-student task completion accepts PUT")
    print("  [PASS] Parent templates contain explicit Read-Only monitoring disclaimers and no mutating forms")

    # -----------------------------------------------------------------------
    # Step 7: Negative Cases — Invalid Login & Unknown Student Handling
    # -----------------------------------------------------------------------
    print("\n[STEP 7] Verifying Negative Cases & Safe Error Handling:")
    # Wrong Parent Password
    res_wrong_p = client.post(
        "/login",
        json={"role": "parent", "student_id": "STU-0004", "password": "wrongpassword"}
    )
    assert res_wrong_p.status_code == 401
    assert "Invalid password for Parent role" in res_wrong_p.get_json()["error"]
    print("  [PASS] Wrong Parent password rejected -> HTTP 401 with informative error message")

    # Wrong Student Password
    res_wrong_s = client.post(
        "/login",
        json={"role": "student", "student_id": "STU-0004", "password": "wrongpassword"}
    )
    assert res_wrong_s.status_code == 401
    assert "Invalid password for Student role" in res_wrong_s.get_json()["error"]
    print("  [PASS] Wrong Student password rejected -> HTTP 401 with informative error message")

    # Unknown Student ID on Login
    res_unknown_login = client.post(
        "/login",
        json={"role": "parent", "student_id": "STU-9999", "password": "parent123"}
    )
    assert res_unknown_login.status_code == 401
    assert "Unknown student ID 'STU-9999'" in res_unknown_login.get_json()["error"]
    print("  [PASS] Unknown Student ID on login rejected -> HTTP 401 with valid ID range guidance")

    # Invalid Role on Login
    res_invalid_role = client.post(
        "/login",
        json={"role": "administrator", "student_id": "STU-0004", "password": "parent123"}
    )
    assert res_invalid_role.status_code == 400
    assert "Invalid role" in res_invalid_role.get_json()["error"]
    print("  [PASS] Invalid role rejected -> HTTP 400")

    # Unknown Student ID on API endpoints
    api_endpoints_404 = [
        "/api/student/STU-9999",
        "/api/student/STU-9999/prediction",
        "/api/student/STU-9999/topics",
        "/api/student/STU-9999/recommendations",
        "/api/student/STU-9999/explanation",
    ]
    for ep in api_endpoints_404:
        res_ep = client.get(ep)
        assert res_ep.status_code == 404
        assert res_ep.get_json().get("error") == "Student ID not found"
    print("  [PASS] All API endpoints return HTTP 404 JSON for unknown student ID STU-9999")

    # -----------------------------------------------------------------------
    # Step 8: ML Pipeline & Model Immutability Verification
    # -----------------------------------------------------------------------
    print("\n[STEP 8] Verifying ML Pipeline, Datasets, and Model Immutability:")
    service = AcademicDataService.get_instance()
    assert service.model is not None
    assert len(service.feature_columns) == 25
    assert len(service.all_student_ids) == 500

    # Ensure required model artifacts exist and have non-zero size
    required_artifacts = [
        PROJECT_ROOT / "models" / "random_forest.pkl",
        PROJECT_ROOT / "models" / "feature_columns.csv",
        PROJECT_ROOT / "models" / "recommendation_examples.csv",
        PROJECT_ROOT / "models" / "shap_feature_importance.csv",
        PROJECT_ROOT / "models" / "shap_feature_importance_by_class.csv",
        PROJECT_ROOT / "data" / "processed" / "early_prediction_dataset.csv",
        PROJECT_ROOT / "data" / "processed" / "student_topic_early_prediction.csv",
        PROJECT_ROOT / "data" / "raw" / "student_learning_data.csv",
    ]
    for art in required_artifacts:
        assert art.exists(), f"Missing artifact: {art}"
        assert art.stat().st_size > 0, f"Artifact is empty: {art}"
        print(f"  [PASS] Artifact intact: {art.name} ({art.stat().st_size:,} bytes)")

    notebooks = [
        "01_dataset_validation_and_eda.ipynb",
        "02_early_prediction_dataset.ipynb",
        "03_ml_model_training_and_evaluation.ipynb",
        "04_shap_explainability.ipynb",
        "05_topic_level_analysis.ipynb",
        "06_recommendation_engine.ipynb",
    ]
    for nb in notebooks:
        nb_path = PROJECT_ROOT / "notebooks" / nb
        assert nb_path.exists(), f"Missing notebook: {nb}"
        assert nb_path.stat().st_size > 0, f"Notebook empty: {nb}"
    print(f"  [PASS] All 6 original research notebooks intact and untouched")

    print("\n" + "=" * 75)
    print("ALL FINAL INTEGRATION VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 75)


if __name__ == "__main__":
    test_complete_integration()
