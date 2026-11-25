"""Verify student summary and detail pages stay focused and distinct."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.app import app


def run_student_dashboard_tests():
    client = app.test_client()
    pages = {
        "/student?student_id=STU-0004": [
            "Welcome back!",
            'id="statusBadge"',
            'id="studentOverallScore"',
            'id="studentAcademicSummaryText"',
            'id="studentOverviewMessage"',
            'id="academicSummarySignals"',
            "Explore subject performance",
            'id="studentProgressTrack"',
            'id="studentProgressBar"',
            'id="studentTotalLogins"',
            'id="studentTotalResources"',
            'id="studentTotalPractice"',
        ],
        "/student/performance?student_id=STU-0004": [
            'id="perfOverallScore"',
            'id="perfAttendance"',
            'id="perfQuiz"',
            'id="perfAssignment"',
            'id="perfIA"',
            "Overall Academic Performance",
            "Your Academic Summary",
            "Subject Performance Overview",
            "Subject-Wise Attendance",
            "Your Strongest Subject",
            "Subject-Wise Performance Chart",
            'id="studentSubjectChart"',
            'id="subjectChartNote"',
            'id="studentAcademicSummaryText"',
            'id="subjectAttendanceList"',
            'id="subjectPerformanceCards"',
            'id="strongestSubjectCard"',
            'id="studentSubjectTableBody"',
            'id="studentDetailedChart"',
            'id="weeklyProgressChartNote"',
            'id="studentProgressEmpty"',
            "Weekly Academic Progress",
            "Attendance*",
        ],
        "/student/ai-insights?student_id=STU-0004": [
            "Predicted Academic Status",
            "Prediction confidence",
            "Status probability",
            "Subjects to Focus On",
            "Areas/Topics You Need to Improve",
            'id="subjectFocusList"',
            'id="assessmentWeaknessList"',
            'id="barLow"',
            'id="barModerate"',
            'id="barHigh"',
        ],
        "/student/recommendations?student_id=STU-0004": [
            'id="studentStudyTipsList"',
            "Your Improvement Areas",
            "Priority-Based Recommendations",
            "Your Personalised Weekly Study Plan",
            'id="recommendationWeeklyStudyPlan"',
            "Today's Study Tasks",
            "Your Weekly Progress",
            "Smart Study Tips",
        ],
    }

    for route, expected in pages.items():
        response = client.get(route)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'id="linkedStudentBadge">STU-0004</strong>' in html
        assert 'id="loadingIndicator" class="loading-indicator" role="status" aria-live="polite"' in html
        for item in expected:
            assert item in html, f"Missing {item} from {route}"
        if route.startswith("/student?"):
            for removed_content in (
                "Your weekly plan",
                "Focus This Week",
                "Quiz preparation",
                "Assignment planning",
                'id="studentFocusWeek"',
                'id="studentMotivation"',
                "Your effort matters.",
            ):
                assert removed_content not in html
        if route.startswith("/student/performance"):
            assert "Personalised Weekly Study Plan" not in html
            assert 'id="recommendationWeeklyStudyPlan"' not in html
            assert "Subjects to Focus On" not in html
            assert "Areas/Topics You Need to Improve" not in html
            assert 'id="subjectFocusList"' not in html
            assert 'id="assessmentWeaknessList"' not in html
        if route.startswith("/student/ai-insights"):
            for removed_content in (
                "MODEL SIGNALS",
                "Signals supporting your progress",
                "Signals to keep an eye on",
                "MODEL EXPLANATION",
                "How features influenced this prediction",
                'id="studentXaiContainer"',
                'id="studentXaiAttentionContainer"',
                'id="studentShapChart"',
                'id="studentShapValues"',
            ):
                assert removed_content not in html
        if route.startswith("/student/recommendations"):
            assert "Personalised Weekly Study Plan" in html
            assert 'id="studentDetailedChart"' not in html
        if route.startswith("/student/performance"):
            section_order = [
                "Overall Academic Performance",
                "Your Academic Summary",
                "Your Strongest Subject",
                "Subject Performance Overview",
                "Subject-Wise Attendance",
                "Subject-Wise Performance Chart",
                "Weekly Academic Progress",
                "Detailed Subject-Wise Analysis",
            ]
            section_positions = [html.index(heading) for heading in section_order]
            assert section_positions == sorted(section_positions)
        assert 'href="/student/topics' not in html
        assert "Topic Progress" not in html

    recommendations_page = client.get(
        "/student/recommendations?student_id=STU-0004"
    ).get_data(as_text=True)
    assert recommendations_page.count("Personalised Weekly Study Plan") == 1

    retired_topic_page = client.get("/student/topics?student_id=STU-0004", follow_redirects=False)
    assert retired_topic_page.status_code == 302
    assert retired_topic_page.headers["Location"].startswith(("/student?", "/student/overview?"))

    overview = client.get("/student?student_id=STU-0004").get_data(as_text=True)
    assert 'id="studentDetailedChart"' not in overview
    assert 'id="perfOverallScore"' not in overview

    subject_response = client.get("/api/student/STU-0004")
    assert subject_response.status_code == 200
    subject_performance = subject_response.get_json()["subject_performance"]
    assert len(subject_performance) == 5
    expected_subject_scores = {
        "Computer Networks": (69.78, 72.07, 68.08, 74.9),
        "Data Structures and Algorithms": (67.06, 68.47, 67.7, 72.87),
        "Database Management Systems": (74.08, 75.89, 75.62, 77.71),
        "Mathematics": (69.56, 68.84, 71.95, 74.65),
        "Operating Systems": (77.34, 74.59, 77.88, 80.68),
    }
    assert {
        subject["subject"]: (
            subject["average_score"],
            subject["quiz_average"],
            subject["assignment_average"],
            subject["internal_assessment_average"],
        )
        for subject in subject_performance
    } == expected_subject_scores
    assert all(
        isinstance(subject[metric], (int, float))
        for subject in subject_performance
        for metric in (
            "average_score",
            "quiz_average",
            "assignment_average",
            "internal_assessment_average",
            "attendance_percentage",
        )
    )
    synthetic_attendance = [
        subject["attendance_percentage"] for subject in subject_performance
    ]
    assert all(65 <= value <= 100 for value in synthetic_attendance)
    assert len(set(synthetic_attendance)) == 5
    repeated_subjects = client.get("/api/student/STU-0004").get_json()["subject_performance"]
    assert [
        subject["attendance_percentage"] for subject in repeated_subjects
    ] == synthetic_attendance
    assert subject_response.get_json()["profile"]["engagement_metrics"][
        "average_attendance_percentage"
    ] == 98.59


if __name__ == "__main__":
    run_student_dashboard_tests()
