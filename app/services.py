"""Academic Support Backend Service Layer.

Provides lightweight, read-only data access, model inference, topic analysis,
precomputed recommendations, and parent-friendly SHAP explanations.

Data boundary:
- Only Weeks 1-6 early features and metrics are exposed as current student progress.
- Weeks 7-10 outcome targets are never exposed as current student progress.
"""

from __future__ import annotations

import hashlib
import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import joblib
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Windows Smart App Control (SAC) Compatibility Shim
# ---------------------------------------------------------------------------
# In Windows 11 with Smart App Control enabled, unsigned native C extensions
# (.pyd) may be blocked. scikit-learn's Tree module imports sklearn.neighbors,
# which transitively imports SGDClassifier's _sgd_fast C-extension.
# Since RandomForestClassifier does not use SGD, we mock _sgd_fast if blocked
# so that joblib.load('models/random_forest.pkl') loads reliably.
if "sklearn.linear_model._sgd_fast" not in sys.modules:
    try:
        import sklearn.linear_model._sgd_fast  # noqa: F401
    except Exception:
        mock_sgd = types.ModuleType("sklearn.linear_model._sgd_fast")

        class _LossFunction:
            pass

        for _name in [
            "LossFunction",
            "Regression",
            "Classification",
            "ModifiedHuber",
            "Hinge",
            "SquaredHinge",
            "Log",
            "SquaredLoss",
            "Huber",
            "EpsilonInsensitive",
            "SquaredEpsilonInsensitive",
        ]:
            setattr(mock_sgd, _name, _LossFunction)
        mock_sgd._plain_sgd32 = None
        mock_sgd._plain_sgd64 = None
        sys.modules["sklearn.linear_model._sgd_fast"] = mock_sgd


# ---------------------------------------------------------------------------
# Project Filepaths & Configuration
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"

EARLY_DATA_PATH = DATA_DIR / "processed" / "early_prediction_dataset.csv"
STUDENT_TOPIC_PATH = DATA_DIR / "processed" / "student_topic_early_prediction.csv"
TOPIC_SUMMARY_PATH = DATA_DIR / "processed" / "topic_summary.csv"
RAW_DATA_PATH = DATA_DIR / "raw" / "student_learning_data.csv"
MODEL_PATH = MODELS_DIR / "random_forest.pkl"
FEATURE_COLUMNS_PATH = MODELS_DIR / "feature_columns.csv"
RECOMMENDATIONS_CSV_PATH = MODELS_DIR / "recommendation_examples.csv"
SHAP_GLOBAL_PATH = MODELS_DIR / "shap_feature_importance.csv"
SHAP_CLASS_PATH = MODELS_DIR / "shap_feature_importance_by_class.csv"

# Target class labels matching existing model training
CLASS_LABELS = {0: "Low", 1: "Moderate", 2: "High"}
CLASS_NAMES_TO_INDEX = {v: k for k, v in CLASS_LABELS.items()}

# Human-readable labels for parent dashboard presentation
FEATURE_LABELS = {
    "average_topic_score": "Average Topic Performance",
    "question_accuracy": "Practice Question Accuracy",
    "average_assignment_score": "Assignment Score Average",
    "average_quiz_score": "Quiz Score Average",
    "average_internal_assessment_score": "Internal Assessment Score",
    "topic_score_trend": "Topic Performance Trend",
    "quiz_score_trend": "Quiz Performance Trend",
    "attendance_trend": "Attendance Trend",
    "assignment_score_trend": "Assignment Score Trend",
    "total_questions_correct": "Correct Practice Questions",
    "average_attendance_percentage": "Class Attendance Rate",
    "average_practice_hours": "Weekly Practice Time",
    "total_practice_hours": "Total Practice Hours",
    "average_lms_login_count": "LMS Portal Logins",
    "average_lms_resource_views": "Study Material Views",
    "total_lms_resource_views": "Total Material Views",
    "total_lms_login_count": "Total LMS Logins",
    "total_questions_attempted": "Total Practice Questions Attempted",
    "average_practice_sessions": "Practice Session Frequency",
    "total_practice_sessions": "Total Practice Sessions",
    "quiz_score_standard_deviation": "Quiz Score Consistency",
    "attendance_standard_deviation": "Attendance Consistency",
    "assignment_score_standard_deviation": "Assignment Consistency",
    "topic_score_standard_deviation": "Topic Performance Consistency",
    "early_weeks_observed": "Observed Weeks",
}


# ---------------------------------------------------------------------------
# Service Class
# ---------------------------------------------------------------------------
class AcademicDataService:
    """Singleton service that loads models, datasets, and SHAP artifacts once on startup."""

    _instance: Optional[AcademicDataService] = None

    def __init__(self) -> None:
        self.model = None
        self.shap_explainer = None
        self.feature_columns: List[str] = []
        self.early_df: pd.DataFrame = pd.DataFrame()
        self.cohort_means: Dict[str, float] = {}
        self.student_topic_df: pd.DataFrame = pd.DataFrame()
        self.topic_summary_df: pd.DataFrame = pd.DataFrame()
        self.recommendations_df: pd.DataFrame = pd.DataFrame()
        self.shap_class_df: pd.DataFrame = pd.DataFrame()
        self.shap_global_df: pd.DataFrame = pd.DataFrame()
        self.weekly_early_summary: Dict[str, List[Dict[str, Any]]] = {}
        self.topic_to_subject_map: Dict[str, str] = {}
        self.all_student_ids: List[str] = []
        self._load_all_artifacts()

    @classmethod
    def get_instance(cls) -> AcademicDataService:
        if cls._instance is None:
            cls._instance = AcademicDataService()
        return cls._instance

    def _load_all_artifacts(self) -> None:
        """Load and cache all models, datasets, and SHAP metadata into memory."""
        # 1. Load trained Random Forest model and exact feature columns
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Model file not found: {MODEL_PATH}")
        self.model = joblib.load(MODEL_PATH)

        if not FEATURE_COLUMNS_PATH.exists():
            raise FileNotFoundError(f"Feature columns file not found: {FEATURE_COLUMNS_PATH}")
        self.feature_columns = pd.read_csv(FEATURE_COLUMNS_PATH)["feature"].tolist()

        # 2. Load early prediction dataset (Weeks 1-6)
        if not EARLY_DATA_PATH.exists():
            raise FileNotFoundError(f"Early prediction dataset not found: {EARLY_DATA_PATH}")
        self.early_df = pd.read_csv(EARLY_DATA_PATH).set_index("student_id")
        self.all_student_ids = sorted(self.early_df.index.tolist())

        # Precompute cohort means for relative comparison in explanations
        self.cohort_means = {
            col: float(self.early_df[col].mean())
            for col in self.feature_columns
            if col in self.early_df.columns
        }

        # 3. Load topic-level early records
        if not STUDENT_TOPIC_PATH.exists():
            raise FileNotFoundError(f"Student topic early dataset not found: {STUDENT_TOPIC_PATH}")
        self.student_topic_df = pd.read_csv(STUDENT_TOPIC_PATH)

        # 4. Load topic summary & map topic to subject
        if not TOPIC_SUMMARY_PATH.exists():
            raise FileNotFoundError(f"Topic summary dataset not found: {TOPIC_SUMMARY_PATH}")
        self.topic_summary_df = pd.read_csv(TOPIC_SUMMARY_PATH)
        self.topic_to_subject_map = dict(
            zip(self.topic_summary_df["topic"], self.topic_summary_df["subject"])
        )

        # 5. Load precomputed recommendations
        if RECOMMENDATIONS_CSV_PATH.exists():
            self.recommendations_df = pd.read_csv(RECOMMENDATIONS_CSV_PATH)
        else:
            self.recommendations_df = pd.DataFrame(
                columns=["student_id", "predicted_status", "topic", "reason", "recommended_action", "priority"]
            )

        # 6. Load SHAP feature importance artifacts
        if SHAP_CLASS_PATH.exists():
            self.shap_class_df = pd.read_csv(SHAP_CLASS_PATH)
        if SHAP_GLOBAL_PATH.exists():
            self.shap_global_df = pd.read_csv(SHAP_GLOBAL_PATH)

        # 7. Precompute weekly early progression (Weeks 1-6 only) from raw data
        if RAW_DATA_PATH.exists():
            raw_data = pd.read_csv(
                RAW_DATA_PATH,
                usecols=[
                    "student_id",
                    "week",
                    "attendance_percentage",
                    "quiz_score",
                    "assignment_score",
                    "internal_assessment_score",
                    "topic_score",
                ],
            )
            # Filter strictly to Weeks 1-6 (Early window)
            early_raw = raw_data[raw_data["week"].between(1, 6)]
            weekly_grouped = (
                early_raw.groupby(["student_id", "week"], as_index=False)
                .agg(
                    attendance=("attendance_percentage", "mean"),
                    quiz=("quiz_score", "mean"),
                    assignment=("assignment_score", "mean"),
                    internal_assessment=("internal_assessment_score", "mean"),
                    topic_score=("topic_score", "mean"),
                )
                .round(2)
            )

            for sid, group in weekly_grouped.groupby("student_id"):
                self.weekly_early_summary[sid] = [
                    {
                        "week": int(row["week"]),
                        "attendance": float(row["attendance"]),
                        "quiz": float(row["quiz"]),
                        "assignment": float(row["assignment"]),
                        "internal_assessment": float(row["internal_assessment"]),
                        "topic_score": float(row["topic_score"]),
                    }
                    for _, row in group.sort_values("week").iterrows()
                ]

    def validate_student_id(self, student_id: str) -> str:
        """Validate that the given student ID exists in the dataset."""
        if not student_id or not isinstance(student_id, str):
            raise ValueError("Student ID must be a non-empty string.")
        clean_id = student_id.strip()
        if clean_id not in self.early_df.index:
            raise KeyError(
                f"Student ID '{clean_id}' not found. Available IDs range from {self.all_student_ids[0]} to {self.all_student_ids[-1]}."
            )
        return clean_id

    def get_all_students(self) -> List[str]:
        """Return list of all 500 anonymized student IDs."""
        return list(self.all_student_ids)

    def get_student_profile(self, student_id: str) -> Dict[str, Any]:
        """Return Weeks 1-6 academic performance, engagement metrics, and weekly history.
        
        Strictly excludes Weeks 7-10 outcome data.
        """
        sid = self.validate_student_id(student_id)
        row = self.early_df.loc[sid]

        profile = {
            "student_id": sid,
            "early_weeks_observed": int(row["early_weeks_observed"]),
            "academic_metrics": {
                "average_topic_score": round(float(row["average_topic_score"]), 2),
                "topic_score_trend": round(float(row["topic_score_trend"]), 3),
                "average_quiz_score": round(float(row["average_quiz_score"]), 2),
                "quiz_score_trend": round(float(row["quiz_score_trend"]), 3),
                "average_assignment_score": round(float(row["average_assignment_score"]), 2),
                "assignment_score_trend": round(float(row["assignment_score_trend"]), 3),
                "average_internal_assessment_score": round(
                    float(row["average_internal_assessment_score"]), 2
                ),
            },
            "engagement_metrics": {
                "average_attendance_percentage": round(
                    float(row["average_attendance_percentage"]), 2
                ),
                "attendance_trend": round(float(row["attendance_trend"]), 3),
                "average_lms_login_count": round(float(row["average_lms_login_count"]), 1),
                "total_lms_login_count": int(row["total_lms_login_count"]),
                "average_lms_resource_views": round(float(row["average_lms_resource_views"]), 1),
                "total_lms_resource_views": int(row["total_lms_resource_views"]),
                "average_practice_sessions": round(float(row["average_practice_sessions"]), 1),
                "total_practice_sessions": int(row["total_practice_sessions"]),
                "average_practice_hours": round(float(row["average_practice_hours"]), 2),
                "total_practice_hours": round(float(row["total_practice_hours"]), 2),
                "total_questions_attempted": int(row["total_questions_attempted"]),
                "total_questions_correct": int(row["total_questions_correct"]),
                "question_accuracy_percentage": round(float(row["question_accuracy"]) * 100, 1),
            },
            "weekly_progression": self.weekly_early_summary.get(sid, []),
        }
        return profile

    def get_student_prediction(self, student_id: str) -> Dict[str, Any]:
        """Predict academic difficulty using the existing trained Random Forest."""
        sid = self.validate_student_id(student_id)

        # Extract strictly the 25 trained features in exact feature order
        student_features = self.early_df.loc[[sid]][self.feature_columns]

        predicted_class_idx = int(self.model.predict(student_features)[0])
        probabilities = self.model.predict_proba(student_features)[0]
        predicted_label = CLASS_LABELS.get(predicted_class_idx, "Unknown")

        status_metadata = {
            "Low": {
                "status_badge": "On Track / Low Risk",
                "badge_color": "success",
                "description": "Student demonstrates steady early mastery and engagement. Low risk of academic difficulty.",
            },
            "Moderate": {
                "status_badge": "Moderate Risk / Monitor",
                "badge_color": "warning",
                "description": "Student shows mixed performance or early downward trends in specific topics. Active monitoring recommended.",
            },
            "High": {
                "status_badge": "High Risk / Attention Needed",
                "badge_color": "danger",
                "description": "Student exhibits early learning struggle, reduced practice, or score declines. Proactive academic support recommended.",
            },
        }

        meta = status_metadata.get(
            predicted_label,
            {
                "status_badge": predicted_label,
                "badge_color": "secondary",
                "description": "Status determined based on Weeks 1-6 early indicator analysis.",
            },
        )

        return {
            "student_id": sid,
            "predicted_difficulty": predicted_label,
            "predicted_class_index": predicted_class_idx,
            "status_badge": meta["status_badge"],
            "badge_color": meta["badge_color"],
            "description": meta["description"],
            "probabilities": {
                CLASS_LABELS[i]: round(float(probabilities[i]), 4)
                for i in range(len(probabilities))
            },
            "confidence_percentage": round(float(probabilities[predicted_class_idx]) * 100, 1),
        }

    def get_student_topics(self, student_id: str) -> List[Dict[str, Any]]:
        """Return all 25 topic records for the student based only on Weeks 1-6 early features.
        
        Strictly excludes any Weeks 7-10 future outcome columns.
        """
        sid = self.validate_student_id(student_id)

        student_topics = self.student_topic_df[self.student_topic_df["student_id"] == sid].copy()
        rec_rows = self.recommendations_df[self.recommendations_df["student_id"] == sid]
        rec_map = {row["topic"]: row for _, row in rec_rows.iterrows()}

        topics_result = []
        for _, row in student_topics.iterrows():
            topic_name = str(row["topic"])
            subject_name = str(row["subject"])
            early_score = round(float(row["average_early_topic_score"]), 2)
            trend = round(float(row["early_topic_score_trend"]), 3)
            accuracy = round(float(row["early_question_accuracy"]) * 100, 1)
            practice_hours = round(float(row["average_early_practice_hours"]), 2)

            if topic_name in rec_map:
                rec_info = rec_map[topic_name]
                priority = str(rec_info["priority"])
                needs_attention = True
                reasons = [r.strip() for r in str(rec_info["reason"]).split(";") if r.strip()]
            else:
                priority = "Satisfactory"
                needs_attention = False
                reasons = []

            topics_result.append({
                "subject": subject_name,
                "topic": topic_name,
                "early_topic_score": early_score,
                "early_topic_score_trend": trend,
                "early_question_accuracy_percentage": accuracy,
                "average_early_practice_hours": practice_hours,
                "average_early_quiz_score": round(float(row["average_early_quiz_score"]), 2),
                "average_early_assignment_score": round(
                    float(row["average_early_assignment_score"]), 2
                ),
                "priority": priority,
                "needs_attention": needs_attention,
                "reasons": reasons,
            })

        # Sort priority topics first, then by lowest score
        priority_order = {"High": 0, "Medium": 1, "Support": 2, "Satisfactory": 3}
        topics_result.sort(
            key=lambda x: (priority_order.get(x["priority"], 4), x["early_topic_score"])
        )
        return topics_result

    def get_student_subject_performance(self, student_id: str) -> List[Dict[str, Any]]:
        """Return early-period subject averages and stable synthetic demo attendance."""
        sid = self.validate_student_id(student_id)
        student_rows = self.student_topic_df[
            self.student_topic_df["student_id"] == sid
        ]
        subject_averages = (
            student_rows.groupby("subject", sort=True)
            .agg(
                average_score=("average_early_topic_score", "mean"),
                quiz_average=("average_early_quiz_score", "mean"),
                assignment_average=("average_early_assignment_score", "mean"),
                internal_assessment_average=(
                    "average_early_internal_assessment_score",
                    "mean",
                ),
            )
            .reset_index()
        )

        used_attendance_values: Set[int] = set()
        subject_performance = []
        for _, row in subject_averages.iterrows():
            subject_performance.append({
                "subject": str(row["subject"]),
                "average_score": round(float(row["average_score"]), 2),
                "quiz_average": round(float(row["quiz_average"]), 2),
                "assignment_average": round(float(row["assignment_average"]), 2),
                "internal_assessment_average": round(
                    float(row["internal_assessment_average"]), 2
                ),
                "attendance_percentage": self._synthetic_subject_attendance(
                    sid, str(row["subject"]), used_attendance_values
                ),
            })
        return subject_performance

    @staticmethod
    def _synthetic_subject_attendance(
        student_id: str, subject: str, used_values: Set[int]
    ) -> int:
        """Create a stable, distinct 65–100% demo value; this is not attendance data."""
        digest = hashlib.sha256(f"{student_id}:{subject}".encode("utf-8")).digest()
        value = 65 + int.from_bytes(digest[:8], byteorder="big") % 36
        while value in used_values:
            value = 65 + (value - 64) % 36
        used_values.add(value)
        return value

    def get_student_recommendations(self, student_id: str) -> Dict[str, Any]:
        """Return personalized recommendations reusing precomputed models/recommendation_examples.csv."""
        sid = self.validate_student_id(student_id)

        rec_rows = self.recommendations_df[self.recommendations_df["student_id"] == sid]

        topics_needing_attention = []
        for _, row in rec_rows.iterrows():
            topic_name = str(row["topic"])
            subject_name = self.topic_to_subject_map.get(topic_name, "General")
            topics_needing_attention.append({
                "subject": subject_name,
                "topic": topic_name,
                "priority": str(row["priority"]),
                "reason": str(row["reason"]),
                "recommended_action": str(row["recommended_action"]),
            })

        if topics_needing_attention:
            high_priority_count = sum(
                1 for t in topics_needing_attention if t["priority"] == "High"
            )
            if high_priority_count > 0:
                parent_summary = (
                    f"Identified {len(topics_needing_attention)} topic(s) requiring attention, "
                    f"including {high_priority_count} high-priority area(s). Focus on consistent "
                    f"daily practice and reviewing core concepts."
                )
            else:
                parent_summary = (
                    f"Identified {len(topics_needing_attention)} topic(s) that could benefit from "
                    f"guided review to prevent future score drop."
                )

            parental_guidance = [
                "Encourage short, focused daily study intervals (25-30 minutes) rather than late cramming.",
                "Review the listed priority topics and confirm whether homework and practice sets for these areas are completed.",
                "Ask your child to explain the key concept of the flagged topic to you; teaching concepts solidifies understanding.",
                "Reach out to the course instructor or academic peer tutoring if difficulty in high-priority topics persists.",
            ]
        else:
            parent_summary = (
                "No urgent topic weaknesses detected. The student is progressing satisfactorily across all early topics."
            )
            parental_guidance = [
                "Continue supporting healthy study habits and consistent attendance.",
                "Encourage your child to maintain their regular practice routine.",
                "Acknowledge their strong performance and proactive engagement.",
            ]

        return {
            "student_id": sid,
            "topics_needing_attention": topics_needing_attention,
            "parent_summary": parent_summary,
            "parental_guidance": parental_guidance,
        }

    def get_student_explanation(self, student_id: str) -> Dict[str, Any]:
        """Preserve existing explanation fields and add student-specific local SHAP values."""
        sid = self.validate_student_id(student_id)
        prediction_info = self.get_student_prediction(sid)
        predicted_label = prediction_info["predicted_difficulty"]

        student_row = self.early_df.loc[sid]

        # Use class-level SHAP rankings
        if not self.shap_class_df.empty:
            class_shap = self.shap_class_df[self.shap_class_df["class"] == predicted_label]
            top_ranked = class_shap.head(6)
        else:
            top_ranked = pd.DataFrame()

        factors = []
        narratives = []

        if not top_ranked.empty:
            for _, r in top_ranked.iterrows():
                feat = r["feature"]
                shap_val = float(r["mean_absolute_shap_value"])
                label = FEATURE_LABELS.get(feat, feat.replace("_", " ").title())

                val = float(student_row[feat])
                cohort_val = self.cohort_means.get(feat, val)
                diff = val - cohort_val

                # Assess whether student metric supported this predicted category
                if predicted_label == "Low":
                    # For low risk, higher scores / accuracy are positive
                    is_positive = diff >= 0
                    direction = "supported" if is_positive else "varied"
                    impact = "Positive" if is_positive else "Neutral"
                    if is_positive:
                        narrative = f"{label} is above cohort average ({val:.1f} vs avg {cohort_val:.1f}), supporting an On Track status."
                    else:
                        narrative = f"{label} shows minor variation ({val:.1f} vs avg {cohort_val:.1f}), but overall performance remains strong."
                elif predicted_label == "Moderate":
                    is_lower = diff < 0
                    direction = "supported" if is_lower else "reduced"
                    impact = "Moderate Risk Indicator" if is_lower else "Stabilizing Factor"
                    if is_lower:
                        narrative = f"{label} ({val:.1f}) is slightly below the class average ({cohort_val:.1f}), indicating need for monitoring."
                    else:
                        narrative = f"{label} ({val:.1f}) remains steady and helps prevent deeper difficulty."
                else:  # High risk
                    is_struggling = diff < 0
                    direction = "supported" if is_struggling else "countered"
                    impact = "High Risk Factor" if is_struggling else "Positive Buffer"
                    if is_struggling:
                        narrative = f"{label} ({val:.1f}) is noticeably below expected benchmark ({cohort_val:.1f}), contributing to elevated risk."
                    else:
                        narrative = f"{label} ({val:.1f}) provides a positive foundation despite other struggling areas."

                factors.append({
                    "feature": feat,
                    "label": label,
                    "student_value": round(val, 2),
                    "cohort_average": round(cohort_val, 2),
                    "shap_importance": round(shap_val, 4),
                    "impact": impact,
                    "direction": direction,
                })
                narratives.append(narrative)

        return {
            "student_id": sid,
            "predicted_difficulty": predicted_label,
            "top_contributing_factors": factors[:5],
            "narrative_explanations": narratives[:5],
            "local_shap_values": self.get_student_local_shap_values(sid, prediction_info),
            "interpretability_note": (
                "SHAP (Explainable AI) identifies which academic and behavioral factors "
                "had the greatest influence on the AI difficulty prediction. These insights guide "
                "personalized recommendations to support the student's learning."
            ),
            "local_shap_note": (
                "Local SHAP values show how each feature moved the model's class probabilities "
                "for this student. They describe model influence, not cause or guaranteed outcomes."
            ),
        }

    def get_student_local_shap_values(
        self, student_id: str, prediction_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return actual per-student TreeSHAP values for each predicted class probability."""
        import shap

        if self.shap_explainer is None:
            self.shap_explainer = shap.TreeExplainer(self.model)

        student_features = self.early_df.loc[[student_id]][self.feature_columns]
        shap_explanation = self.shap_explainer(student_features)
        shap_values = np.asarray(shap_explanation.values, dtype=float)
        if shap_values.ndim == 2:
            shap_values = shap_values[:, :, np.newaxis]
        if shap_values.ndim != 3 or shap_values.shape[0] != 1:
            raise ValueError(f"Unexpected local SHAP shape: {shap_values.shape}")
        if (
            shap_values.shape[1] != len(self.feature_columns)
            and shap_values.shape[2] == len(self.feature_columns)
        ):
            shap_values = np.transpose(shap_values, (0, 2, 1))

        classes = list(self.model.classes_)
        if (
            shap_values.shape[1] != len(self.feature_columns)
            or shap_values.shape[2] != len(classes)
        ):
            raise ValueError(
                f"Local SHAP dimensions do not match model features/classes: {shap_values.shape}"
            )

        base_values = np.asarray(shap_explanation.base_values, dtype=float)
        if base_values.ndim == 2 and base_values.shape[0] == 1:
            base_values = base_values[0]
        base_values = base_values.reshape(-1)
        if base_values.size != len(classes):
            raise ValueError(f"Unexpected local SHAP base-value shape: {base_values.shape}")

        predicted_class = int(prediction_info["predicted_class_index"])
        predicted_indices = [
            index for index, value in enumerate(classes)
            if int(value) == predicted_class
        ]
        low_class = CLASS_NAMES_TO_INDEX["Low"]
        low_indices = [
            index for index, value in enumerate(classes)
            if int(value) == low_class
        ]
        if len(predicted_indices) != 1 or len(low_indices) != 1:
            raise ValueError("Model classes do not contain the predicted and Low classes.")

        predicted_index = predicted_indices[0]
        probabilities = np.asarray(self.model.predict_proba(student_features)[0], dtype=float)
        reconstructed_probabilities = base_values + shap_values[0].sum(axis=0)
        if not np.allclose(reconstructed_probabilities, probabilities, rtol=1e-4, atol=1e-4):
            raise ValueError("Local SHAP contributions do not reconstruct model probabilities.")

        student_row = self.early_df.loc[student_id]
        factors = []
        for feature_index, feature in enumerate(self.feature_columns):
            class_contributions = {
                CLASS_LABELS[int(class_value)]: round(
                    float(shap_values[0, feature_index, class_index]), 10
                )
                for class_index, class_value in enumerate(classes)
            }
            factors.append({
                "feature": feature,
                "label": FEATURE_LABELS.get(feature, feature.replace("_", " ").title()),
                "student_value": round(float(student_row[feature]), 4),
                "cohort_average": round(
                    float(self.cohort_means.get(feature, student_row[feature])), 4
                ),
                "predicted_class_shap_value": class_contributions[prediction_info["predicted_difficulty"]],
                "on_track_shap_value": class_contributions["Low"],
                "class_shap_values": class_contributions,
            })
        factors.sort(
            key=lambda factor: abs(factor["predicted_class_shap_value"]),
            reverse=True,
        )

        return {
            "predicted_class": prediction_info["predicted_difficulty"],
            "output_type": "class_probability",
            "base_value": round(float(base_values[predicted_index]), 10),
            "predicted_probability": round(float(probabilities[predicted_index]), 10),
            "reconstructed_probability": round(
                float(reconstructed_probabilities[predicted_index]), 10
            ),
            "factors": factors,
        }

    def get_complete_student_dashboard(self, student_id: str) -> Dict[str, Any]:
        """Combine profile, prediction, topic analysis, recommendations, and SHAP into a unified dictionary."""
        sid = self.validate_student_id(student_id)

        profile = self.get_student_profile(sid)
        prediction = self.get_student_prediction(sid)
        subject_performance = self.get_student_subject_performance(sid)
        topics = self.get_student_topics(sid)
        recommendations = self.get_student_recommendations(sid)
        explanation = self.get_student_explanation(sid)

        flagged_topics = [t for t in topics if t["needs_attention"]]

        return {
            "metadata": {
                "student_id": sid,
                "monitoring_period": "Weeks 1–6 (Early Prediction Window)",
                "target_period": "Weeks 7–10 (Early Warning Outlook)",
                "access_role": "Parent (Read-Only Monitoring)",
                "system_description": "Explainable AI Early Academic Warning & Personalized Learning Support",
            },
            "profile": profile,
            "prediction": prediction,
            "subject_performance": subject_performance,
            "summary_counts": {
                "total_topics_monitored": len(topics),
                "topics_needing_attention_count": len(flagged_topics),
                "high_priority_count": sum(1 for t in flagged_topics if t["priority"] == "High"),
                "medium_priority_count": sum(1 for t in flagged_topics if t["priority"] == "Medium"),
                "support_priority_count": sum(1 for t in flagged_topics if t["priority"] == "Support"),
            },
            "topics": topics,
            "recommendations": recommendations,
            "explanation": explanation,
        }


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------
def get_all_students() -> List[str]:
    return AcademicDataService.get_instance().get_all_students()


def get_student_profile(student_id: str) -> Dict[str, Any]:
    return AcademicDataService.get_instance().get_student_profile(student_id)


def get_student_prediction(student_id: str) -> Dict[str, Any]:
    return AcademicDataService.get_instance().get_student_prediction(student_id)


def get_student_topics(student_id: str) -> List[Dict[str, Any]]:
    return AcademicDataService.get_instance().get_student_topics(student_id)


def get_student_recommendations(student_id: str) -> Dict[str, Any]:
    return AcademicDataService.get_instance().get_student_recommendations(student_id)


def get_student_explanation(student_id: str) -> Dict[str, Any]:
    return AcademicDataService.get_instance().get_student_explanation(student_id)


def get_complete_student_dashboard(student_id: str) -> Dict[str, Any]:
    return AcademicDataService.get_instance().get_complete_student_dashboard(student_id)
