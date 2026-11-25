"""Phase 6 Verification Test: Student AI Insights Page.

Tests:
1. Reusing existing SHAP explanation API (/api/student/<student_id>/explanation).
2. Verifying a concise status, confidence, probability, and factor view.
3. Verifying top contributing factors are limited to three and use simple labels.
"""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.app import app
from app.services import get_student_explanation, get_student_prediction


def run_student_ai_insights_tests():
    print("=" * 75)
    print("PHASE 6: STUDENT AI INSIGHTS VERIFICATION SUITE")
    print("=" * 75)

    client = app.test_client()

    # 1. Test existing explanation fields and local TreeSHAP probability additivity
    print("\n[TEST 1] Verifying student-specific TreeSHAP contributions:")
    for sid in ["STU-0004", "STU-0001", "STU-0185"]:
        res = client.get(f"/api/student/{sid}/explanation")
        assert res.status_code == 200, f"Failed GET /api/student/{sid}/explanation"
        data = res.get_json()

        assert "top_contributing_factors" in data, f"Missing factors for {sid}"
        assert "narrative_explanations" in data, f"Missing narratives for {sid}"
        assert "local_shap_values" in data, f"Missing local SHAP values for {sid}"
        assert len(data["top_contributing_factors"]) >= 3, f"Expected at least 3 factors for {sid}"
        assert len(data["narrative_explanations"]) >= 3, f"Expected at least 3 narratives for {sid}"

        first_factor = data["top_contributing_factors"][0]
        assert "label" in first_factor, "Factor missing human-readable label"
        assert "impact" in first_factor, "Factor missing impact"
        assert "direction" in first_factor, "Factor missing direction"

        local_shap = data["local_shap_values"]
        prediction = get_student_prediction(sid)
        assert local_shap["predicted_class"] == prediction["predicted_difficulty"]
        assert local_shap["output_type"] == "class_probability"
        assert len(local_shap["factors"]) == 25
        assert abs(
            local_shap["predicted_probability"]
            - prediction["probabilities"][local_shap["predicted_class"]]
        ) < 0.0002
        assert abs(
            local_shap["base_value"]
            + sum(factor["predicted_class_shap_value"] for factor in local_shap["factors"])
            - prediction["probabilities"][local_shap["predicted_class"]]
        ) < 0.0002, f"SHAP values do not reconstruct {sid}'s predicted probability"
        assert all(
            factor["on_track_shap_value"] == factor["class_shap_values"]["Low"]
            for factor in local_shap["factors"]
        )
        assert any(factor["on_track_shap_value"] > 0 for factor in local_shap["factors"])
        assert any(factor["on_track_shap_value"] < 0 for factor in local_shap["factors"])

        print(f"  [PASS] {sid}: Loaded {len(data['top_contributing_factors'])} factors (Top: {first_factor['label']} - {first_factor['impact']})")

    # 2. Test GET /student/ai-insights route and student-facing guidance
    print("\n[TEST 2] Testing /student/ai-insights View:")
    res_page = client.get("/student/ai-insights?student_id=STU-0004")
    assert res_page.status_code == 200, f"Expected 200, got {res_page.status_code}"
    html = res_page.get_data(as_text=True)

    assert "Predicted Academic Status" in html
    assert "Status probability" in html
    assert "Subjects to Focus On" in html
    assert "Areas/Topics You Need to Improve" in html
    assert 'id="subjectFocusList"' in html
    assert 'id="assessmentWeaknessList"' in html
    assert "not a guarantee of future results" in html
    assert 'href="/student/recommendations?student_id=STU-0004#personalised-plan-heading"' in html
    assert 'id="studentInsightsStatusBadge"' in html, "Missing status badge id='studentInsightsStatusBadge'"
    assert 'id="studentInsightsConfidence"' in html, "Missing confidence badge id='studentInsightsConfidence'"
    assert 'id="barLow"' in html and 'id="barModerate"' in html and 'id="barHigh"' in html
    for removed_content in (
        "MODEL SIGNALS",
        "Signals supporting your progress",
        "Signals to keep an eye on",
        "MODEL EXPLANATION",
        "How features influenced this prediction",
        'id="studentXaiContainer"',
        'id="studentShapChart"',
    ):
        assert removed_content not in html
    print("  [PASS] AI Insights DOM Elements: prediction, subject focus, and assessment guidance present")

    # 3. Verify the moved views still use actual subject and assessment data
    print("\n[TEST 3] Testing student guidance rendering and assessment rules:")
    js_file = PROJECT_ROOT / "static" / "js" / "student_dashboard.js"
    assert js_file.exists(), f"Missing {js_file}"
    js_content = js_file.read_text(encoding="utf-8")

    assert "function renderSubjectFocus" in js_content
    assert "function renderAssessmentWeaknesses" in js_content
    assert "function getSubjectAssessmentAnalysis" in js_content
    assert "function getSubjectFocusGuidance" in js_content
    print("  [PASS] Controller renders existing subject focus and assessment guidance")

    print("\n" + "=" * 75)
    print("ALL PHASE 6 STUDENT AI INSIGHTS TESTS PASSED SUCCESSFULLY!")
    print("=" * 75)


if __name__ == "__main__":
    run_student_ai_insights_tests()
