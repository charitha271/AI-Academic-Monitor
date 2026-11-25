"""Reusable validation helpers for the raw synthetic learning dataset."""

from pathlib import Path

import pandas as pd


EXPECTED_COLUMNS = [
    "student_id",
    "week",
    "subject",
    "topic",
    "attendance_percentage",
    "lectures_attended",
    "lectures_conducted",
    "quiz_score",
    "assignment_score",
    "internal_assessment_score",
    "lms_login_count",
    "lms_resource_views",
    "practice_sessions",
    "practice_hours",
    "questions_attempted",
    "questions_correct",
    "topic_score",
    "academic_difficulty",
]


def load_dataset(path=None):
    """Load the raw CSV without modifying it."""
    if path is None:
        path = Path(__file__).resolve().parents[1] / "data" / "raw" / "student_learning_data.csv"
    return pd.read_csv(path)


def validation_summary(dataset):
    """Return structural validation facts for the supplied dataset."""
    records_per_student = dataset.groupby("student_id").size()
    student_subject_counts = dataset.groupby("student_id")["subject"].nunique()
    student_topic_counts = dataset.groupby("student_id")["topic"].nunique()
    return {
        "shape": dataset.shape,
        "columns_match_expected": list(dataset.columns) == EXPECTED_COLUMNS,
        "missing_values": int(dataset.isna().sum().sum()),
        "duplicate_rows": int(dataset.duplicated().sum()),
        "unique_students": int(dataset["student_id"].nunique()),
        "unique_subjects": int(dataset["subject"].nunique()),
        "unique_topics": int(dataset["topic"].nunique()),
        "unique_weeks": int(dataset["week"].nunique()),
        "all_students_have_10_weeks": bool(records_per_student.eq(250).all()),
        "all_students_have_5_subjects": bool(student_subject_counts.eq(5).all()),
        "all_students_have_25_topics": bool(student_topic_counts.eq(25).all()),
        "records_per_student": records_per_student,
        "records_per_subject": dataset.groupby("subject").size(),
        "records_per_topic": dataset.groupby("topic").size(),
        "records_per_week": dataset.groupby("week").size(),
    }


def main():
    dataset = load_dataset()
    summary = validation_summary(dataset)
    print(f"Dataset shape: {summary['shape']}")
    print(f"Missing values: {summary['missing_values']}")
    print(f"Duplicate rows: {summary['duplicate_rows']}")
    print(f"Expected columns: {summary['columns_match_expected']}")
    print(f"Students with 10 weeks: {summary['all_students_have_10_weeks']}")
    print(f"Students with 5 subjects: {summary['all_students_have_5_subjects']}")
    print(f"Students with 25 topics: {summary['all_students_have_25_topics']}")


if __name__ == "__main__":
    main()
