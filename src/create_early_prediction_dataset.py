"""Create a leakage-controlled student-level dataset for early prediction.

Inputs are aggregated only from weeks 1-6. The future target is independently
constructed from weeks 7-10 and is not copied from the raw target column.
"""

from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = PROJECT_ROOT / "data" / "raw" / "student_learning_data.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_PATH = PROCESSED_DIR / "early_prediction_dataset.csv"
INFO_PATH = PROCESSED_DIR / "early_prediction_dataset_info.txt"
EARLY_WEEKS = range(1, 7)
FUTURE_WEEKS = range(7, 11)
TARGET_LABELS = {0: "Low", 1: "Moderate", 2: "High"}


def _weekly_means(data):
    """Collapse repeated topic rows to one student-week observation."""
    return data.groupby(["student_id", "week"], as_index=False).agg(
        attendance_percentage=("attendance_percentage", "mean"),
        quiz_score=("quiz_score", "mean"),
        assignment_score=("assignment_score", "mean"),
        internal_assessment_score=("internal_assessment_score", "mean"),
        lms_login_count=("lms_login_count", "mean"),
        lms_resource_views=("lms_resource_views", "mean"),
        practice_sessions=("practice_sessions", "mean"),
        practice_hours=("practice_hours", "mean"),
        topic_score=("topic_score", "mean"),
    )


def _slope(data, value_column):
    """Return a student's least-squares weekly trend for one measure."""
    if len(data) < 2 or data[value_column].nunique() < 2:
        return 0.0
    return float(np.polyfit(data["week"], data[value_column], 1)[0])


def _future_difficulty(future_mean, future_change):
    """Construct the weeks 7-10 future academic difficulty target.

    The existing raw target uses weeks 8-10 and compares week 10 with week 8.
    That target is unsuitable for the requested weeks 7-10 outcome window.
    This target instead uses the mean topic_score across weeks 7-10 and the
    change from week 7 to week 10. The same thresholds are retained so the
    meaning of Low, Moderate, and High remains comparable to the generator:

    - High (2): future mean < 48, or future mean < 58 with change <= -8.
    - Moderate (1): future mean < 68, or future change <= -10.
    - Low (0): all other future outcomes.
    """
    if future_mean < 48 or (future_mean < 58 and future_change <= -8):
        return 2
    if future_mean < 68 or future_change <= -10:
        return 1
    return 0


def _build_early_features(early_data):
    """Build one row per student using early weeks only."""
    weekly = _weekly_means(early_data)
    early_features = weekly.groupby("student_id").agg(
        early_weeks_observed=("week", "nunique"),
        average_attendance_percentage=("attendance_percentage", "mean"),
        attendance_standard_deviation=("attendance_percentage", "std"),
        average_quiz_score=("quiz_score", "mean"),
        quiz_score_standard_deviation=("quiz_score", "std"),
        average_assignment_score=("assignment_score", "mean"),
        assignment_score_standard_deviation=("assignment_score", "std"),
        average_internal_assessment_score=("internal_assessment_score", "mean"),
        average_lms_login_count=("lms_login_count", "mean"),
        total_lms_login_count=("lms_login_count", "sum"),
        average_lms_resource_views=("lms_resource_views", "mean"),
        total_lms_resource_views=("lms_resource_views", "sum"),
        average_practice_sessions=("practice_sessions", "mean"),
        total_practice_sessions=("practice_sessions", "sum"),
        average_practice_hours=("practice_hours", "mean"),
        total_practice_hours=("practice_hours", "sum"),
        average_topic_score=("topic_score", "mean"),
        topic_score_standard_deviation=("topic_score", "std"),
    )
    trend_features = weekly.groupby("student_id").apply(
        lambda group: pd.Series({
            "attendance_trend": _slope(group, "attendance_percentage"),
            "quiz_score_trend": _slope(group, "quiz_score"),
            "assignment_score_trend": _slope(group, "assignment_score"),
            "topic_score_trend": _slope(group, "topic_score"),
        }),
        include_groups=False,
    )
    question_features = early_data.groupby("student_id").agg(
        total_questions_attempted=("questions_attempted", "sum"),
        total_questions_correct=("questions_correct", "sum"),
    )
    question_features["question_accuracy"] = (
        question_features["total_questions_correct"]
        / question_features["total_questions_attempted"]
    )
    features = early_features.join(trend_features).join(question_features)
    return features.reset_index()


def _build_future_target(raw_data):
    """Build one future target per student from weeks 7-10 only."""
    future = raw_data[raw_data["week"].isin(FUTURE_WEEKS)].copy()
    weekly = future.groupby(["student_id", "week"])["topic_score"].mean().unstack()
    if set(weekly.columns) != set(FUTURE_WEEKS):
        raise ValueError("Future target window does not contain every week 7-10")
    target = pd.DataFrame(index=weekly.index)
    target["future_mean_topic_score"] = future.groupby("student_id")["topic_score"].mean()
    target["future_score_change"] = weekly[10] - weekly[7]
    target["academic_difficulty"] = [
        _future_difficulty(mean_score, change)
        for mean_score, change in zip(
            target["future_mean_topic_score"], target["future_score_change"]
        )
    ]
    return target.reset_index()


def create_dataset(raw_data):
    """Return the processed one-row-per-student early prediction dataset."""
    early_data = raw_data[raw_data["week"].isin(EARLY_WEEKS)].copy()
    features = _build_early_features(early_data)
    target = _build_future_target(raw_data)
    dataset = features.merge(target[["student_id", "academic_difficulty"]], on="student_id", how="inner")
    return dataset


def validate_dataset(processed, raw_data):
    """Validate dimensions, target coverage, and week separation."""
    expected_features = {
        "early_weeks_observed", "average_attendance_percentage",
        "attendance_standard_deviation", "attendance_trend", "average_quiz_score",
        "quiz_score_standard_deviation", "quiz_score_trend", "average_assignment_score",
        "assignment_score_standard_deviation", "assignment_score_trend",
        "average_internal_assessment_score", "average_lms_login_count",
        "total_lms_login_count", "average_lms_resource_views", "total_lms_resource_views",
        "average_practice_sessions", "total_practice_sessions", "average_practice_hours",
        "total_practice_hours", "total_questions_attempted", "total_questions_correct",
        "question_accuracy", "average_topic_score", "topic_score_standard_deviation",
        "topic_score_trend",
    }
    actual_features = set(processed.columns) - {"student_id", "academic_difficulty"}
    if processed.shape[0] != raw_data["student_id"].nunique():
        raise ValueError("Processed row count does not equal unique student count")
    if processed["student_id"].duplicated().any():
        raise ValueError("Duplicate students found")
    if actual_features != expected_features:
        raise ValueError("Processed feature columns do not match the expected set")
    if processed.isna().any().any():
        raise ValueError("Missing values found in processed dataset")
    if not processed["academic_difficulty"].isin(TARGET_LABELS).all():
        raise ValueError("Unexpected target class found")
    if not processed["early_weeks_observed"].eq(len(EARLY_WEEKS)).all():
        raise ValueError("Early features do not contain exactly weeks 1-6")
    if set(raw_data.loc[raw_data["week"].isin(EARLY_WEEKS), "week"]) != set(EARLY_WEEKS):
        raise ValueError("Early input window is incomplete")
    if set(raw_data.loc[raw_data["week"].isin(FUTURE_WEEKS), "week"]) != set(FUTURE_WEEKS):
        raise ValueError("Future target window is incomplete")


def write_info(processed):
    """Write the preprocessing and leakage documentation file."""
    counts = processed["academic_difficulty"].value_counts().sort_index()
    percentages = (counts / len(processed) * 100).round(2)
    lines = [
        "Early Prediction Dataset Information",
        "====================================",
        f"Source dataset: {RAW_PATH}",
        f"Output dataset: {OUTPUT_PATH}",
        f"Number of students: {len(processed)}",
        f"Rows: {len(processed)} (one row per student)",
        "Input weeks: 1-6 only",
        "Target weeks: 7-10 only",
        "",
        "Feature construction:",
        "- Weekly repeated topic rows were collapsed to student-week means where indicators repeat across topics.",
        "- Early features include means, totals, standard deviations, and least-squares weekly slopes for attendance, quiz, assignment, topic score, LMS activity, practice, and question behavior.",
        "- Question attempts and correct answers are summed across early student-topic records; question_accuracy is correct divided by attempted.",
        "",
        "Exact target construction:",
        "- The raw academic_difficulty target was inspected and found to use weeks 8-10: future mean topic_score plus week-10 minus week-8 change.",
        "- It was not copied because the requested outcome window is weeks 7-10.",
        "- New future_mean_topic_score is the student's mean topic_score across weeks 7-10.",
        "- New future_score_change is mean topic_score in week 10 minus mean topic_score in week 7.",
        "- High (2): future mean < 48, or future mean < 58 and change <= -8.",
        "- Moderate (1): future mean < 68, or change <= -10.",
        "- Low (0): all other future outcomes.",
        "- The thresholds are retained from the generator for comparability; the weeks 7-10 target is a new documented construction.",
        "",
        "Target distribution:",
    ]
    lines.extend(f"- {TARGET_LABELS[index]} ({index}): {counts.get(index, 0)} students ({percentages.get(index, 0):.2f}%)" for index in TARGET_LABELS)
    lines.extend([
        "",
        "Leakage precautions:",
        "- No week 7-10 values are used in input feature construction.",
        "- academic_difficulty is a target only and is not an input feature.",
        "- Use student-level splits; random row-level splits are inappropriate for the raw repeated-record data.",
        "- Consider time-aware validation when simulating deployment over sequential cohorts or periods.",
    ])
    INFO_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    raw_data = pd.read_csv(RAW_PATH)
    processed = create_dataset(raw_data)
    validate_dataset(processed, raw_data)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    processed.to_csv(OUTPUT_PATH, index=False)
    write_info(processed)
    counts = processed["academic_difficulty"].value_counts().sort_index().to_dict()
    print(f"Students: {processed['student_id'].nunique()}")
    print(f"Features: {len(processed.columns) - 2}")
    print("Target: academic_difficulty (weeks 7-10 future performance)")
    print("Input weeks: 1-6")
    print("Target weeks: 7-10")
    print(f"Missing values: {int(processed.isna().sum().sum())}")
    print(f"Duplicate students: {int(processed['student_id'].duplicated().sum())}")
    print("Leakage checks: PASS (features use weeks 1-6; target uses weeks 7-10)")
    print("ML-ready: YES for preprocessing/modeling experiments, pending split and validation design")
    print(f"Target distribution: {counts}")
    print(f"Saved: {OUTPUT_PATH}")
    print(f"Metadata: {INFO_PATH}")


if __name__ == "__main__":
    main()