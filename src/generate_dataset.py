"""Generate a reproducible synthetic dataset for the academic-support project."""

from pathlib import Path

import numpy as np
import pandas as pd


RANDOM_SEED = 20260915
NUM_STUDENTS = 500
NUM_WEEKS = 10

SUBJECT_TOPICS = {
    "Data Structures and Algorithms": [
        "Arrays", "Linked Lists", "Trees", "Graph Algorithms", "Dynamic Programming"
    ],
    "Database Management Systems": [
        "ER Model", "Normalization", "SQL", "SQL Joins", "Transactions"
    ],
    "Operating Systems": [
        "Processes and Threads", "CPU Scheduling", "Memory Management", "Deadlocks", "File Systems"
    ],
    "Computer Networks": [
        "OSI and TCP/IP", "IP Addressing", "Routing", "Transport Layer", "Network Security"
    ],
    "Mathematics": [
        "Probability", "Statistics", "Linear Algebra", "Calculus", "Discrete Mathematics"
    ],
}

DIFFICULTY_BY_TOPIC = {
    "Arrays": 0.05, "Linked Lists": 0.10, "Trees": 0.25,
    "Graph Algorithms": 0.35, "Dynamic Programming": 0.45,
    "ER Model": 0.00, "Normalization": 0.15, "SQL": 0.05,
    "SQL Joins": 0.20, "Transactions": 0.30,
    "Processes and Threads": 0.15, "CPU Scheduling": 0.20,
    "Memory Management": 0.30, "Deadlocks": 0.35, "File Systems": 0.10,
    "OSI and TCP/IP": 0.00, "IP Addressing": 0.10, "Routing": 0.25,
    "Transport Layer": 0.20, "Network Security": 0.30,
    "Probability": 0.20, "Statistics": 0.10, "Linear Algebra": 0.25,
    "Calculus": 0.35, "Discrete Mathematics": 0.30,
}


def _bounded_normal(rng, mean, standard_deviation, lower, upper):
    """Draw a noisy value while keeping it in a realistic range."""
    return float(np.clip(rng.normal(mean, standard_deviation), lower, upper))


def _difficulty_class(future_mean, future_change):
    """Assign a future outcome class from weeks 8-10, not week 1 inputs.

    High difficulty is assigned when later performance is low or when a low
    future mean is paired with a substantial decline. Moderate difficulty
    covers borderline later performance or a meaningful decline. The target
    is deterministic for a fixed generated trajectory.
    """
    if future_mean < 48 or (future_mean < 58 and future_change <= -8):
        return 2
    if future_mean < 68 or future_change <= -10:
        return 1
    return 0


def generate_dataset():
    """Generate student-week-topic observations with correlated noise."""
    rng = np.random.default_rng(RANDOM_SEED)
    subjects = list(SUBJECT_TOPICS)
    topics = [topic for subject in subjects for topic in SUBJECT_TOPICS[subject]]

    # Latent student traits create correlations without making any observed
    # field a deterministic transformation of another field.
    student_profiles = {}
    for student_number in range(1, NUM_STUDENTS + 1):
        student_id = f"STU-{student_number:04d}"
        student_profiles[student_id] = {
            "attendance_baseline": rng.normal(82, 9),
            "engagement_baseline": rng.normal(0, 0.8),
            "ability": rng.normal(0, 8),
            "subject_strength": {subject: rng.normal(0, 7) for subject in subjects},
            "topic_affinity": {topic: rng.normal(0, 5) for topic in topics},
            "trend": rng.choice([-1, 0, 1], p=[0.18, 0.54, 0.28]),
            "trend_strength": rng.uniform(0.35, 1.20),
        }

    rows = []
    for student_id, profile in student_profiles.items():
        for week in range(1, NUM_WEEKS + 1):
            weekly_motivation = rng.normal(0, 2.5)
            trajectory_effect = profile["trend"] * profile["trend_strength"] * (week - 5.5)
            attendance = _bounded_normal(
                rng, profile["attendance_baseline"] + 1.5 * trajectory_effect,
                5.5, 45, 100
            )
            engagement = (
                profile["engagement_baseline"] + 0.035 * (attendance - 80)
                + 0.12 * trajectory_effect + rng.normal(0, 0.65)
            )
            lectures_conducted = int(rng.choice([2, 3, 4], p=[0.25, 0.55, 0.20]))
            lectures_attended = int(np.clip(
                round(lectures_conducted * attendance / 100 + rng.normal(0, 0.25)),
                0, lectures_conducted
            ))
            login_count = int(np.clip(round(3.5 + 1.8 * engagement + rng.normal(0, 1.8)), 0, 18))
            resource_views = int(np.clip(
                round(7 + 4.2 * engagement + rng.normal(0, 4.0)), 0, 45
            ))
            practice_sessions = int(np.clip(
                round(2.2 + 0.9 * engagement + rng.normal(0, 1.4)), 0, 10
            ))
            practice_hours = round(float(np.clip(
                practice_sessions * rng.uniform(0.35, 0.85) + rng.normal(0, 0.35),
                0, 12
            )), 2)

            for subject in subjects:
                subject_effect = profile["subject_strength"][subject]
                for topic in SUBJECT_TOPICS[subject]:
                    learning_signal = (
                        profile["ability"] + subject_effect + profile["topic_affinity"][topic]
                        - 18 * DIFFICULTY_BY_TOPIC[topic] + 0.45 * (attendance - 80)
                        + 1.7 * engagement + 1.4 * practice_hours
                        + trajectory_effect + weekly_motivation
                    )
                    topic_score = _bounded_normal(rng, 63 + learning_signal, 7.5, 10, 100)
                    quiz_score = _bounded_normal(
                        rng, topic_score - 2 + 0.15 * resource_views, 9, 0, 100
                    )
                    assignment_score = _bounded_normal(
                        rng, topic_score + 0.9 * practice_hours - 1, 8, 0, 100
                    )
                    internal_assessment_score = _bounded_normal(
                        rng, topic_score + 0.25 * (attendance - 80), 6.5, 0, 100
                    )
                    questions_attempted = int(np.clip(
                        round(7 + 1.2 * practice_sessions + rng.normal(0, 2.5)),
                        1, 30
                    ))
                    correctness_probability = float(np.clip(
                        0.35 + topic_score / 180 + rng.normal(0, 0.035), 0.15, 0.95
                    ))
                    questions_correct = int(
                        rng.binomial(questions_attempted, correctness_probability)
                    )
                    rows.append({
                        "student_id": student_id,
                        "week": week,
                        "subject": subject,
                        "topic": topic,
                        "attendance_percentage": round(attendance, 2),
                        "lectures_attended": lectures_attended,
                        "lectures_conducted": lectures_conducted,
                        "quiz_score": round(quiz_score, 2),
                        "assignment_score": round(assignment_score, 2),
                        "internal_assessment_score": round(internal_assessment_score, 2),
                        "lms_login_count": login_count,
                        "lms_resource_views": resource_views,
                        "practice_sessions": practice_sessions,
                        "practice_hours": practice_hours,
                        "questions_attempted": questions_attempted,
                        "questions_correct": questions_correct,
                        "topic_score": round(topic_score, 2),
                    })

    dataset = pd.DataFrame(rows)

    # The outcome uses only later performance. For each student, aggregate
    # weeks 8-10 topic scores and compare week 10 with week 8. This target
    # must be excluded when training an early predictor.
    future_scores = dataset.loc[dataset["week"].between(8, 10)]
    future_summary = future_scores.groupby(["student_id", "week"])["topic_score"].mean().unstack()
    future_summary["future_mean"] = future_scores.groupby("student_id")["topic_score"].mean()
    future_summary["future_change"] = future_summary[10] - future_summary[8]
    future_summary["academic_difficulty"] = future_summary.apply(
        lambda row: _difficulty_class(row["future_mean"], row["future_change"]), axis=1
    )
    dataset["academic_difficulty"] = dataset["student_id"].map(
        future_summary["academic_difficulty"]
    )
    return dataset


def validate_dataset(dataset):
    """Print required checks and raise an error for unexpected violations."""
    expected_rows = NUM_STUDENTS * NUM_WEEKS * sum(map(len, SUBJECT_TOPICS.values()))
    expected_columns = [
        "student_id", "week", "subject", "topic", "attendance_percentage",
        "lectures_attended", "lectures_conducted", "quiz_score", "assignment_score",
        "internal_assessment_score", "lms_login_count", "lms_resource_views",
        "practice_sessions", "practice_hours", "questions_attempted", "questions_correct",
        "topic_score", "academic_difficulty",
    ]
    if dataset.shape != (expected_rows, len(expected_columns)):
        raise ValueError(f"Unexpected dataset shape: {dataset.shape}")
    if list(dataset.columns) != expected_columns:
        raise ValueError("Dataset columns do not match the expected schema")
    if dataset.isna().any().any():
        raise ValueError("Unexpected missing values found")
    if not dataset["student_id"].str.fullmatch(r"STU-\d{4}").all():
        raise ValueError("Student IDs are not anonymized as expected")
    if not set(dataset["academic_difficulty"].unique()).issubset({0, 1, 2}):
        raise ValueError("Unexpected academic_difficulty class found")

    print(f"Dataset shape: {dataset.shape}")
    print("First 5 rows:")
    print(dataset.head().to_string(index=False))
    print("\nSummary statistics:")
    print(dataset.describe(include="all").transpose().to_string())
    print("\nClass distribution of academic_difficulty:")
    print(dataset[["student_id", "academic_difficulty"]].drop_duplicates()["academic_difficulty"].value_counts().sort_index())
    print(f"\nUnexpected missing values: {int(dataset.isna().sum().sum())}")
    print("Student IDs anonymized: True")
    print(f"Unique students: {dataset['student_id'].nunique()}")
    print(f"Unique subjects: {dataset['subject'].nunique()}")
    print(f"Unique topics: {dataset['topic'].nunique()}")
    print(f"Unique weeks: {dataset['week'].nunique()}")


def main():
    dataset = generate_dataset()
    output_path = Path(__file__).resolve().parents[1] / "data" / "raw" / "student_learning_data.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(output_path, index=False)
    validate_dataset(dataset)
    print(f"\nSaved dataset to: {output_path}")


if __name__ == "__main__":
    main()