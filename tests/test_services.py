"""Verification test for Phase 2: app/services.py."""

import json
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.services import (
    get_all_students,
    get_student_profile,
    get_student_prediction,
    get_student_topics,
    get_student_recommendations,
    get_student_explanation,
    get_complete_student_dashboard,
)


def run_tests():
    print("=" * 60)
    print("PHASE 2 VERIFICATION SUITE")
    print("=" * 60)

    # 1. Test get_all_students
    all_students = get_all_students()
    print(f"[PASS] get_all_students: Loaded {len(all_students)} students.")
    assert len(all_students) == 500, f"Expected 500 students, got {len(all_students)}"
    assert all_students[0] == "STU-0001", f"First student should be STU-0001, got {all_students[0]}"
    assert all_students[-1] == "STU-0500", f"Last student should be STU-0500, got {all_students[-1]}"

    # Test targeted students
    test_ids = ["STU-0004", "STU-0001", "STU-0185"]

    for sid in test_ids:
        print("\n" + "-" * 50)
        print(f"Testing Student: {sid}")
        print("-" * 50)

        # 2. Test get_student_prediction
        pred = get_student_prediction(sid)
        print(f"  Prediction: {pred['predicted_difficulty']} ({pred['status_badge']})")
        print(f"  Confidence: {pred['confidence_percentage']}%")
        print(f"  Probabilities: {pred['probabilities']}")
        assert "predicted_difficulty" in pred
        assert "probabilities" in pred

        # 3. Test get_student_profile
        prof = get_student_profile(sid)
        print(f"  Observed Weeks: {prof['early_weeks_observed']}")
        print(f"  Attendance: {prof['engagement_metrics']['average_attendance_percentage']}%")
        print(f"  Quiz Avg: {prof['academic_metrics']['average_quiz_score']}")
        print(f"  Assignment Avg: {prof['academic_metrics']['average_assignment_score']}")
        print(f"  IA Score: {prof['academic_metrics']['average_internal_assessment_score']}")
        print(f"  Question Accuracy: {prof['engagement_metrics']['question_accuracy_percentage']}%")
        print(f"  Weekly Progression entries: {len(prof['weekly_progression'])}")
        assert len(prof['weekly_progression']) == 6, "Expected 6 early weeks"

        # 4. Test get_student_topics
        topics = get_student_topics(sid)
        flagged = [t for t in topics if t["needs_attention"]]
        print(f"  Total Topics: {len(topics)} (Expected 25)")
        print(f"  Topics Needing Attention: {len(flagged)}")
        assert len(topics) == 25, f"Expected 25 topics, got {len(topics)}"
        for ft in flagged[:2]:
            print(f"    * [{ft['priority']}] {ft['subject']} -> {ft['topic']}: Score={ft['early_topic_score']}, Trend={ft['early_topic_score_trend']}, Reasons={ft['reasons']}")

        # 5. Test get_student_recommendations
        recs = get_student_recommendations(sid)
        print(f"  Recommendations Count: {len(recs['topics_needing_attention'])}")
        print(f"  Parent Summary: {recs['parent_summary']}")
        print(f"  Guidance Tips: {len(recs['parental_guidance'])} tips provided")
        assert "topics_needing_attention" in recs
        assert "parental_guidance" in recs

        # 6. Test get_student_explanation
        exp = get_student_explanation(sid)
        top_factor = exp["top_contributing_factors"][0]
        print(f"  Top SHAP Factor: {top_factor['label']} ({top_factor['impact']})")
        print(f"  Sample Narrative: {exp['narrative_explanations'][0]}")
        assert len(exp["top_contributing_factors"]) > 0

        # 7. Test get_complete_student_dashboard
        dash = get_complete_student_dashboard(sid)
        print(f"  Dashboard generated successfully. Keys: {list(dash.keys())}")
        # Verify JSON serializability
        json_output = json.dumps(dash)
        assert len(json_output) > 0, "Dashboard payload must be valid JSON"
        print(f"  Dashboard JSON payload size: {len(json_output)} bytes")

    # 8. Test Unknown Student ID Error Handling
    print("\n" + "-" * 50)
    print("Testing Unknown Student ID Error Handling:")
    print("-" * 50)
    try:
        get_student_profile("STU-9999")
        raise AssertionError("Should have raised KeyError for unknown student ID")
    except KeyError as exc:
        print(f"  [PASS] Correctly raised KeyError: {exc}")

    print("\n" + "=" * 60)
    print("ALL PHASE 2 VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
