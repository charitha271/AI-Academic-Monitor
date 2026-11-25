"""Verify the single, read-only parent monitoring dashboard."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.app import app


def run_parent_dashboard_tests():
    client = app.test_client()
    pages = {
        "/parent?student_id=STU-0004": [
            'id="statusBadge"',
            'id="parentProgressSummary"',
            'id="kpiOverallScore"',
            'id="kpiAttendance"',
            'id="kpiAttendanceNote"',
            'id="kpiQuiz"',
            'id="kpiAssignment"',
            'id="kpiIA"',
            'id="overviewTrendChart"',
            'id="parentTrendNote"',
            'id="parentSupportSuggestions"',
            "Overall Performance",
            "Overall Academic Performance",
            "Weekly Academic Progress",
            "Suggestions for Parents",
            "Read-only view",
            "Student ID:",
        ],
    }

    for route, expected in pages.items():
        response = client.get(route)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "Parent Access (Read-Only)" in html
        assert 'id="loadingIndicator" class="loading-indicator" role="status" aria-live="polite"' in html
        assert 'id="linkedStudentBadge">STU-0004</strong>' in html
        for item in expected:
            assert item in html, f"Missing {item} from {route}"
        assert "Academic Progress Summary" not in html
        assert 'id="overviewGuidanceSummary"' not in html
        assert html.count('class="nav-item') == 1
        assert "/parent/performance" not in html
        assert "/parent/ai-insights" not in html
        assert "Prediction confidence" not in html
        assert "data-nav=\"topics\"" not in html
        assert "data-nav=\"support\"" not in html
        assert "Curriculum Topic" not in html

    for route in [
        "/parent/performance?student_id=STU-0004",
        "/parent/ai-insights?student_id=STU-0004",
        "/parent/topics?student_id=STU-0004",
        "/parent/support?student_id=STU-0004",
    ]:
        response = client.get(route)
        assert response.status_code == 302
        assert response.headers["Location"].startswith(("/parent?", "/parent/overview?"))


if __name__ == "__main__":
    run_parent_dashboard_tests()
