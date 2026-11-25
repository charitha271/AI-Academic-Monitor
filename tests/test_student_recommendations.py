"""Verify personalised recommendation pages and persistent task completion."""

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.app import app
from app.services import AcademicDataService


def run_student_recommendation_tests():
    client = app.test_client()
    performance_html = client.get(
        "/student/performance?student_id=STU-0004"
    ).get_data(as_text=True)
    recommendations_html = client.get(
        "/student/recommendations?student_id=STU-0004"
    ).get_data(as_text=True)

    assert "Weekly Academic Progress" in performance_html
    assert "Personalised Weekly Study Plan" not in performance_html
    assert "recommendationWeeklyStudyPlan" not in performance_html
    assert recommendations_html.count("Your Personalised Weekly Study Plan") == 1
    assert 'id="recommendationWeeklyStudyPlan"' in recommendations_html
    assert 'id="todayStudyTasks"' in recommendations_html
    assert 'id="weeklyTaskProgressBar"' in recommendations_html
    assert "Your Personalised Weekly Study Plan" not in client.get(
        "/student?student_id=STU-0004"
    ).get_data(as_text=True)

    service = AcademicDataService.get_instance()
    profiles = {
        sid: service.get_student_subject_performance(sid)
        for sid in ("STU-0004", "STU-0001", "STU-0185")
    }
    weakest_subjects = {
        sid: min(subjects, key=lambda subject: subject["average_score"])["subject"]
        for sid, subjects in profiles.items()
    }
    assert len(set(weakest_subjects.values())) > 1
    assert weakest_subjects["STU-0004"] == "Data Structures and Algorithms"
    assert weakest_subjects["STU-0001"] == "Mathematics"

    with tempfile.TemporaryDirectory() as temp_dir:
        original_database = app.config["STUDY_TASK_DATABASE"]
        app.config["STUDY_TASK_DATABASE"] = str(
            Path(temp_dir) / "study-tasks.sqlite3"
        )
        try:
            initial = client.get(
                "/api/student/STU-0004/study-tasks"
            )
            assert initial.status_code == 200
            assert initial.get_json()["completions"] == {}
            week_start = initial.get_json()["week_start"]

            completed = client.put(
                "/api/student/STU-0004/study-tasks",
                json={
                    "task_id": "monday-data-structures-practise-quiz",
                    "completed": True,
                },
            )
            assert completed.status_code == 200
            assert completed.get_json()["completed"] is True
            assert completed.get_json()["week_start"] == week_start

            refreshed = client.get(
                "/api/student/STU-0004/study-tasks"
            ).get_json()
            assert refreshed["completions"][
                "monday-data-structures-practise-quiz"
            ] is True

            other_student = client.get(
                "/api/student/STU-0001/study-tasks"
            ).get_json()
            assert other_student["completions"] == {}

            reverted = client.put(
                "/api/student/STU-0004/study-tasks",
                json={
                    "task_id": "monday-data-structures-practise-quiz",
                    "completed": False,
                },
            )
            assert reverted.status_code == 200
            assert client.get(
                "/api/student/STU-0004/study-tasks"
            ).get_json()["completions"][
                "monday-data-structures-practise-quiz"
            ] is False

            invalid = client.put(
                "/api/student/STU-0004/study-tasks",
                json={"task_id": "invalid task id", "completed": True},
            )
            assert invalid.status_code == 400
            malformed = client.put(
                "/api/student/STU-0004/study-tasks",
                json={"task_id": "monday-test"},
            )
            assert malformed.status_code == 400
            invalid_completion = client.put(
                "/api/student/STU-0004/study-tasks",
                json={"task_id": "monday-test", "completed": 1},
            )
            assert invalid_completion.status_code == 400
            invalid_task_type = client.put(
                "/api/student/STU-0004/study-tasks",
                json={"task_id": ["monday-test"], "completed": True},
            )
            assert invalid_task_type.status_code == 400
            unknown = client.get(
                "/api/student/STU-9999/study-tasks"
            )
            assert unknown.status_code == 404
        finally:
            app.config["STUDY_TASK_DATABASE"] = original_database


if __name__ == "__main__":
    run_student_recommendation_tests()
