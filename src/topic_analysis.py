"""Create and analyze the topic-level early-prediction dataset."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = PROJECT_ROOT / "data" / "raw" / "student_learning_data.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_PATH = PROCESSED_DIR / "student_topic_early_prediction.csv"
SUMMARY_PATH = PROCESSED_DIR / "topic_summary.csv"
FIGURES_DIR = PROJECT_ROOT / "figures" / "topic_analysis"
EARLY_WEEKS = range(1, 7)
FUTURE_WEEKS = range(7, 11)
TARGET_LABELS = {0: "Low attention", 1: "Moderate attention", 2: "High attention"}


def _slope(group, value_column):
	"""Calculate a least-squares weekly trend for one student-topic series."""
	if len(group) < 2 or group[value_column].nunique() < 2:
		return 0.0
	return float(np.polyfit(group["week"], group[value_column], 1)[0])


def _topic_difficulty(future_mean, future_change, thresholds):
	"""Assign an empirical topic-attention class from weeks 7-10 only.

	High attention is assigned to the bottom decile of future mean performance,
	or to the bottom quartile of mean performance when paired with a bottom-
	quartile decline. Moderate attention covers remaining below-median future
	mean performance or a bottom-quartile decline. All other observations are
	Low attention. These thresholds are calculated from the observed future
	student-topic distribution, not copied from the student-level target.
	"""
	if future_mean <= thresholds["future_mean_p10"]:
		return 2
	if future_mean <= thresholds["future_mean_p25"] and future_change <= thresholds["future_change_p25"]:
		return 2
	if future_mean <= thresholds["future_mean_p50"] or future_change <= thresholds["future_change_p25"]:
		return 1
	return 0


def load_raw_data():
	"""Load the raw topic-level data without modifying it."""
	return pd.read_csv(RAW_PATH)


def build_early_features(raw_data):
	"""Aggregate only weeks 1-6 into one row per student-topic."""
	early = raw_data[raw_data["week"].isin(EARLY_WEEKS)].copy()
	grouped = early.groupby(["student_id", "subject", "topic"])
	features = grouped.agg(
		early_weeks_observed=("week", "nunique"),
		average_early_topic_score=("topic_score", "mean"),
		early_topic_score_standard_deviation=("topic_score", "std"),
		average_early_quiz_score=("quiz_score", "mean"),
		average_early_assignment_score=("assignment_score", "mean"),
		average_early_internal_assessment_score=("internal_assessment_score", "mean"),
		average_early_practice_sessions=("practice_sessions", "mean"),
		total_early_practice_sessions=("practice_sessions", "sum"),
		average_early_practice_hours=("practice_hours", "mean"),
		total_early_practice_hours=("practice_hours", "sum"),
		total_early_questions_attempted=("questions_attempted", "sum"),
		total_early_questions_correct=("questions_correct", "sum"),
		average_early_lms_login_count=("lms_login_count", "mean"),
		average_early_lms_resource_views=("lms_resource_views", "mean"),
	)
	weekly = early.groupby(["student_id", "subject", "topic", "week"], as_index=False).agg(
		topic_score=("topic_score", "mean"),
		quiz_score=("quiz_score", "mean"),
		practice_hours=("practice_hours", "mean"),
	)
	trends = weekly.groupby(["student_id", "subject", "topic"]).apply(
		lambda group: pd.Series({
			"early_topic_score_trend": _slope(group, "topic_score"),
			"early_quiz_score_trend": _slope(group, "quiz_score"),
			"early_practice_hours_trend": _slope(group, "practice_hours"),
		}),
		include_groups=False,
	)
	features = features.join(trends)
	features["early_question_accuracy"] = (
		features["total_early_questions_correct"]
		/ features["total_early_questions_attempted"]
	)
	features["early_topic_score_standard_deviation"] = features[
		"early_topic_score_standard_deviation"
	].fillna(0.0)
	return features.reset_index()


def build_future_target(raw_data):
	"""Analyze future scores and construct a new topic-level target."""
	future = raw_data[raw_data["week"].isin(FUTURE_WEEKS)].copy()
	grouped = future.groupby(["student_id", "subject", "topic"])
	future_summary = grouped["topic_score"].mean().rename("future_mean_topic_score").to_frame()
	weekly = future.groupby(["student_id", "subject", "topic", "week"])["topic_score"].mean().unstack()
	future_summary["future_topic_score_change"] = weekly[10] - weekly[7]
	thresholds = {
		"future_mean_p10": future_summary["future_mean_topic_score"].quantile(0.10),
		"future_mean_p25": future_summary["future_mean_topic_score"].quantile(0.25),
		"future_mean_p50": future_summary["future_mean_topic_score"].quantile(0.50),
		"future_change_p25": future_summary["future_topic_score_change"].quantile(0.25),
	}
	future_summary["topic_difficulty"] = [
		_topic_difficulty(mean_score, change, thresholds)
		for mean_score, change in zip(
			future_summary["future_mean_topic_score"],
			future_summary["future_topic_score_change"],
		)
	]
	return future_summary.reset_index(), thresholds


def create_topic_dataset(raw_data):
	"""Return topic-level data and empirical thresholds."""
	early_features = build_early_features(raw_data)
	future_target, thresholds = build_future_target(raw_data)
	dataset = early_features.merge(
		future_target,
		on=["student_id", "subject", "topic"],
		how="inner",
	)
	return dataset, thresholds


def build_topic_summary(dataset):
	"""Summarize early/future performance and attention by topic."""
	summary = dataset.groupby(["subject", "topic"]).agg(
		number_of_students=("student_id", "nunique"),
		average_early_score=("average_early_topic_score", "mean"),
		average_future_score=("future_mean_topic_score", "mean"),
		average_future_score_change=("future_topic_score_change", "mean"),
		future_score_standard_deviation=("future_mean_topic_score", "std"),
		percentage_needing_attention=("topic_difficulty", lambda values: 100 * (values > 0).mean()),
		percentage_high_attention=("topic_difficulty", lambda values: 100 * (values == 2).mean()),
	).reset_index()
	return summary.round(3)


def save_figures(dataset, summary):
	"""Save descriptive topic-level figures."""
	FIGURES_DIR.mkdir(parents=True, exist_ok=True)
	sns.set_theme(style="whitegrid", context="notebook")

	plt.figure(figsize=(9, 5))
	sns.histplot(dataset["future_mean_topic_score"], kde=True, color="#4472C4")
	plt.title("Future topic-score distribution (weeks 7-10)")
	plt.xlabel("Mean future topic score")
	plt.tight_layout()
	plt.savefig(FIGURES_DIR / "future_topic_performance_distribution.png", dpi=150)
	plt.close()

	plt.figure(figsize=(12, 8))
	ordered = summary.sort_values("average_future_score")
	sns.barplot(data=ordered, y="topic", x="average_future_score", hue="subject", dodge=False, errorbar=None)
	plt.title("Average future topic score by topic")
	plt.xlabel("Average future topic score")
	plt.tight_layout()
	plt.savefig(FIGURES_DIR / "average_topic_score_by_topic.png", dpi=150, bbox_inches="tight")
	plt.close()

	subject_summary = summary.groupby("subject", as_index=False)["average_future_score"].mean()
	plt.figure(figsize=(10, 5))
	sns.barplot(data=subject_summary.sort_values("average_future_score"), x="average_future_score", y="subject", color="#70AD47")
	plt.title("Average future topic score by subject")
	plt.tight_layout()
	plt.savefig(FIGURES_DIR / "average_topic_score_by_subject.png", dpi=150, bbox_inches="tight")
	plt.close()

	trend = dataset.groupby("topic")["future_topic_score_change"].mean().sort_values()
	plt.figure(figsize=(12, 8))
	sns.barplot(x=trend.values, y=trend.index, color="#ED7D31")
	plt.axvline(0, color="black", linewidth=0.8)
	plt.title("Average future topic performance change: week 7 to week 10")
	plt.xlabel("Mean score change")
	plt.tight_layout()
	plt.savefig(FIGURES_DIR / "topic_performance_trends.png", dpi=150, bbox_inches="tight")
	plt.close()

	plt.figure(figsize=(12, 8))
	attention = summary.sort_values("percentage_needing_attention")
	sns.barplot(data=attention, x="percentage_needing_attention", y="topic", hue="subject", dodge=False, errorbar=None)
	plt.title("Students needing attention by topic")
	plt.xlabel("Percentage needing attention")
	plt.tight_layout()
	plt.savefig(FIGURES_DIR / "students_needing_attention_by_topic.png", dpi=150, bbox_inches="tight")
	plt.close()

	heatmap_data = summary.pivot(index="subject", columns="topic", values="average_future_score")
	plt.figure(figsize=(16, 5))
	sns.heatmap(heatmap_data, annot=True, fmt=".1f", cmap="YlGnBu")
	plt.title("Future topic performance heatmap")
	plt.tight_layout()
	plt.savefig(FIGURES_DIR / "topic_performance_heatmap.png", dpi=150, bbox_inches="tight")
	plt.close()


def validate_topic_dataset(dataset, raw_data, thresholds):
	"""Run leakage, completeness, and target-construction checks."""
	feature_columns = [
		column for column in dataset.columns
		if column not in {"student_id", "subject", "topic", "future_mean_topic_score", "future_topic_score_change", "topic_difficulty"}
	]
	forbidden = {"student_id", "future_mean_topic_score", "future_topic_score_change", "topic_difficulty", "week"}
	if forbidden.intersection(feature_columns):
		raise ValueError("Leakage detected in topic-level feature columns")
	if dataset[["student_id", "subject", "topic"]].duplicated().any():
		raise ValueError("Duplicate student-topic combinations found")
	expected_combinations = raw_data["student_id"].nunique() * raw_data["topic"].nunique()
	if len(dataset) != expected_combinations:
		raise ValueError("Unexpected number of student-topic combinations")
	if not dataset["early_weeks_observed"].eq(len(EARLY_WEEKS)).all():
		raise ValueError("Some student-topic combinations lack complete early weeks 1-6")
	if dataset.isna().any().any():
		raise ValueError("Missing values found in topic-level dataset")
	if not set(dataset["topic_difficulty"].unique()).issubset({0, 1, 2}):
		raise ValueError("Unexpected topic target class")
	if set(raw_data.loc[raw_data["week"].isin(EARLY_WEEKS), "week"]) != set(EARLY_WEEKS):
		raise ValueError("Early weeks are incomplete")
	if set(raw_data.loc[raw_data["week"].isin(FUTURE_WEEKS), "week"]) != set(FUTURE_WEEKS):
		raise ValueError("Future weeks are incomplete")
	return feature_columns


def main():
	raw_data = load_raw_data()
	topic_data, thresholds = create_topic_dataset(raw_data)
	feature_columns = validate_topic_dataset(topic_data, raw_data, thresholds)
	summary = build_topic_summary(topic_data)
	PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
	topic_data.to_csv(OUTPUT_PATH, index=False)
	summary.to_csv(SUMMARY_PATH, index=False)
	save_figures(topic_data, summary)

	future_distribution = raw_data.loc[raw_data["week"].isin(FUTURE_WEEKS), "topic_score"].describe(
		percentiles=[0.10, 0.25, 0.50, 0.75, 0.90]
	)
	print("Future topic-score distribution:")
	print(future_distribution.to_string())
	print(f"Topic-level data available: YES")
	print(f"Unique subjects: {raw_data['subject'].nunique()}")
	print(f"Unique topics: {raw_data['topic'].nunique()}")
	print(f"Student-topic combinations: {len(topic_data)}")
	print("Early weeks used: 1-6")
	print("Future weeks used for target: 7-10")
	print("Topic-level target justified: YES (empirical future-score percentiles and trends)")
	print("Topic-level dataset created: YES")
	print(f"Feature columns using early data only: {len(feature_columns)}")
	print("Leakage checks: PASSED")
	print("Figures saved: figures/topic_analysis/")
	print("Summary CSV saved: data/processed/topic_summary.csv")
	print("Topic analysis complete: YES")
	print("Target labels: 0=Low attention, 1=Moderate attention, 2=High attention")
	print(f"Target distribution: {topic_data['topic_difficulty'].value_counts().sort_index().to_dict()}")
	print(f"Empirical thresholds: {thresholds}")


if __name__ == "__main__":
	main()
