"""Generate personalized learning-support recommendations from early data.

Recommendations use weeks 1-6 features only. Future topic performance and the
validated topic target are loaded for schema/reference checks but are never
used to determine recommendation priority or action.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EARLY_PATH = PROJECT_ROOT / "data" / "processed" / "early_prediction_dataset.csv"
TOPIC_PATH = PROJECT_ROOT / "data" / "processed" / "student_topic_early_prediction.csv"
TOPIC_SUMMARY_PATH = PROJECT_ROOT / "data" / "processed" / "topic_summary.csv"
MODEL_PATH = PROJECT_ROOT / "models" / "random_forest.pkl"
FEATURE_PATH = PROJECT_ROOT / "models" / "feature_columns.csv"
TEST_IDS_PATH = PROJECT_ROOT / "models" / "test_students.csv"
OUTPUT_DIR = PROJECT_ROOT / "models" / "recommendation_examples"
CSV_PATH = PROJECT_ROOT / "models" / "recommendation_examples.csv"
RULES_PATH = PROJECT_ROOT / "models" / "recommendation_rules.txt"
CLASS_LABELS = {0: "Low", 1: "Moderate", 2: "High"}


# These concepts are limited to the actual topics in the generated dataset.
TOPIC_ACTIONS = {
	"Arrays": "Revise array traversal, searching, and common array operations; complete a small practice set.",
	"Linked Lists": "Review node links, insertion, deletion, and traversal; practice pointer-tracing problems.",
	"Trees": "Review tree traversal and practice preorder, inorder, and postorder problems.",
	"Graph Algorithms": "Revise BFS and DFS and practice graph traversal problems.",
	"Dynamic Programming": "Review recurrence design, memoization, and tabulation through guided problems.",
	"ER Model": "Review entities, relationships, cardinality, and ER diagram construction; complete design exercises.",
	"Normalization": "Review functional dependencies and normal forms; practice decomposition examples.",
	"SQL": "Review SELECT, filtering, grouping, and aggregation; complete topic-specific SQL questions.",
	"SQL Joins": "Review join types and join conditions; practice queries that combine related tables.",
	"Transactions": "Review transaction properties, concurrency, and recovery concepts; complete short checks.",
	"Processes and Threads": "Review process states, thread behavior, and synchronization basics; practice tracing exercises.",
	"CPU Scheduling": "Review scheduling criteria and algorithms; solve scheduling timeline problems.",
	"Memory Management": "Review paging, segmentation, and virtual memory; practice address-translation questions.",
	"Deadlocks": "Review deadlock conditions, prevention, avoidance, and detection; practice resource-allocation examples.",
	"File Systems": "Review files, directories, allocation, and file-system organization; complete short exercises.",
	"OSI and TCP/IP": "Review the layers and compare OSI with TCP/IP; practice protocol-layer classification questions.",
	"IP Addressing": "Review IPv4 addressing, subnetting, and address ranges; practice subnet calculations.",
	"Routing": "Review routing concepts and route selection; practice small routing-table examples.",
	"Transport Layer": "Review transport-layer services, reliability, and flow control; practice protocol questions.",
	"Network Security": "Review common network-security principles and controls; complete concept-check questions.",
	"Probability": "Review sample spaces, events, and probability rules; practice short probability problems.",
	"Statistics": "Review descriptive measures and interpretation; practice calculation and reading exercises.",
	"Linear Algebra": "Review vectors, matrices, and linear systems; practice worked algebra problems.",
	"Calculus": "Review derivative and integral concepts; complete guided calculation practice.",
	"Discrete Mathematics": "Review logic, sets, relations, and counting; practice structured discrete-math problems.",
}


def _load_inputs():
	"""Load artifacts and verify the saved model feature contract."""
	early = pd.read_csv(EARLY_PATH)
	topic = pd.read_csv(TOPIC_PATH)
	topic_summary = pd.read_csv(TOPIC_SUMMARY_PATH)
	model = joblib.load(MODEL_PATH)
	feature_columns = pd.read_csv(FEATURE_PATH)["feature"].tolist()
	if set(feature_columns) != set(early.columns) - {"student_id", "academic_difficulty"}:
		raise ValueError("Saved model features do not match the early dataset")
	if "student_id" in feature_columns or "academic_difficulty" in feature_columns:
		raise ValueError("Identifier or target included in model features")
	if set(topic["topic"].unique()) != set(TOPIC_ACTIONS):
		raise ValueError("Topic action mapping does not match actual dataset topics")
	if not set(topic_summary["topic"].unique()) == set(topic["topic"].unique()):
		raise ValueError("Topic summary topics do not match topic dataset")
	test_ids = pd.read_csv(TEST_IDS_PATH)["student_id"].tolist()
	return early, topic, topic_summary, model, feature_columns, test_ids


def _thresholds(topic_data):
	"""Derive early-signal thresholds from the topic feature distribution."""
	return {
		"early_score_p25": topic_data["average_early_topic_score"].quantile(0.25),
		"trend_p25": topic_data["early_topic_score_trend"].quantile(0.25),
		"accuracy_p25": topic_data["early_question_accuracy"].quantile(0.25),
		"practice_hours_p25": topic_data["average_early_practice_hours"].quantile(0.25),
	}


def _shap_values(model, feature_frame):
	"""Return SHAP values as samples x features x classes for SHAP 0.52."""
	explanation = shap.TreeExplainer(model)(feature_frame)
	values = np.asarray(explanation.values)
	if values.ndim == 2:
		values = values[:, :, None]
	if values.ndim != 3:
		raise ValueError(f"Unexpected SHAP output shape: {values.shape}")
	if values.shape[1] != feature_frame.shape[1] and values.shape[2] == feature_frame.shape[1]:
		values = np.transpose(values, (0, 2, 1))
	if values.shape[1] != feature_frame.shape[1]:
		raise ValueError("SHAP values do not match the saved model feature matrix")
	return values


def _topic_reasons(row, thresholds):
	"""Return evidence-based reasons and a priority score from early signals."""
	reasons = []
	score = 0
	if row["average_early_topic_score"] <= thresholds["early_score_p25"]:
		reasons.append("Lower early topic score")
		score += 3
	if row["early_topic_score_trend"] <= thresholds["trend_p25"]:
		reasons.append("Declining early topic trend")
		score += 2
	if row["early_question_accuracy"] <= thresholds["accuracy_p25"]:
		reasons.append("Lower question accuracy")
		score += 2
	if row["average_early_practice_hours"] <= thresholds["practice_hours_p25"]:
		reasons.append("Reduced early practice activity")
		score += 1
	return reasons, score


def _priority(score):
	if score >= 5:
		return "High"
	if score >= 3:
		return "Medium"
	if score >= 1:
		return "Support"
	return "Monitor"


def _actions(topic, reasons):
	"""Map the observed topic signals to supportive, topic-specific actions."""
	actions = [TOPIC_ACTIONS[topic]]
	if "Declining early topic trend" in reasons:
		actions.append("Review recent prerequisite concepts and complete additional guided practice.")
	if "Lower question accuracy" in reasons:
		actions.append("Practice topic-specific questions and review mistakes after each attempt.")
	if "Reduced early practice activity" in reasons:
		actions.append("Increase practice gradually with one small practice set before the next study session.")
	if "Lower early topic score" in reasons:
		actions.append("Use a concise concept review before attempting the practice set.")
	return actions


def _model_reasons(model, feature_columns, early_row, shap_row, predicted_class):
	"""Return model-contribution reasons, explicitly distinguishing contribution from cause."""
	ranked = pd.DataFrame({"feature": feature_columns, "shap_value": shap_row[0, :, predicted_class]})
	ranked["absolute"] = ranked["shap_value"].abs()
	reasons = []
	feature_text = {
		"average_topic_score": "Average topic score",
		"question_accuracy": "Question accuracy",
		"average_assignment_score": "Assignment performance",
		"average_quiz_score": "Quiz performance",
		"average_internal_assessment_score": "Internal assessment performance",
		"topic_score_trend": "Topic-score trend",
		"average_practice_hours": "Practice activity",
	}
	for _, item in ranked.sort_values("absolute", ascending=False).head(3).iterrows():
		label = feature_text.get(item["feature"], item["feature"])
		direction = "supported" if item["shap_value"] >= 0 else "reduced"
		reasons.append(f"{label} {direction} the {CLASS_LABELS[predicted_class]} model output")
	return reasons


def _build_reports(early, topic_data, model, feature_columns, thresholds, test_ids):
	"""Generate structured reports for all students and detailed examples."""
	feature_frame = early[feature_columns]
	predictions = model.predict(feature_frame)
	probabilities = model.predict_proba(feature_frame)
	shap_values = _shap_values(model, feature_frame)
	early_index = early.set_index("student_id")
	topic_groups = {student_id: group for student_id, group in topic_data.groupby("student_id")}
	reports = {}
	rows = []
	for index, student_id in enumerate(early["student_id"]):
		predicted_class = int(predictions[index])
		student_topics = topic_groups[student_id].copy()
		scored_topics = []
		for _, topic_row in student_topics.iterrows():
			reasons, score = _topic_reasons(topic_row, thresholds)
			if score > 0:
				scored_topics.append({
					"subject": topic_row["subject"],
					"topic": topic_row["topic"],
					"reasons": reasons,
					"score": score,
					"priority": _priority(score),
					"recommended_actions": _actions(topic_row["topic"], reasons),
					"early_score": topic_row["average_early_topic_score"],
					"trend": topic_row["early_topic_score_trend"],
					"question_accuracy": topic_row["early_question_accuracy"],
					"practice_hours": topic_row["average_early_practice_hours"],
				})
		scored_topics.sort(key=lambda item: (-item["score"], item["topic"]))
		scored_topics = scored_topics[:5]
		model_reasons = _model_reasons(model, feature_columns, early_index.loc[student_id], shap_values[index:index + 1], predicted_class)
		reports[student_id] = {
			"student_id": student_id,
			"predicted_learning_status": CLASS_LABELS[predicted_class],
			"predicted_probabilities": {
				CLASS_LABELS[class_index]: float(probabilities[index, class_index])
				for class_index in range(probabilities.shape[1])
			},
			"topics_needing_attention": scored_topics,
			"reasons": model_reasons,
			"recommended_actions": [
				"Prioritize the listed topics with short, topic-specific practice sessions.",
				"Review progress after the next learning cycle; these recommendations do not guarantee improvement.",
			],
			"priority": scored_topics[0]["priority"] if scored_topics else "Monitor",
			"progress": {
				"early_average_topic_score": float(early_index.loc[student_id, "average_topic_score"]),
				"early_topic_score_trend": float(early_index.loc[student_id, "topic_score_trend"]),
				"early_question_accuracy": float(early_index.loc[student_id, "question_accuracy"]),
				"early_practice_hours": float(early_index.loc[student_id, "average_practice_hours"]),
			},
		}
		for topic in scored_topics:
			rows.append({
				"student_id": student_id,
				"predicted_status": CLASS_LABELS[predicted_class],
				"topic": topic["topic"],
				"reason": "; ".join(topic["reasons"]),
				"recommended_action": " ".join(topic["recommended_actions"]),
				"priority": topic["priority"],
			})
	return reports, pd.DataFrame(rows)


def _write_report(report, path):
	"""Write a human-readable support report."""
	lines = [
		f"STUDENT: {report['student_id']}",
		f"LEARNING STATUS: {report['predicted_learning_status']}",
		"",
		"TOPICS NEEDING ATTENTION:",
	]
	if not report["topics_needing_attention"]:
		lines.append("- No high-signal topic rule was triggered; continue monitoring progress.")
	for topic in report["topics_needing_attention"]:
		lines.extend([
			f"- {topic['subject']} - {topic['topic']} [{topic['priority']} priority]",
			f"  Early score: {topic['early_score']:.2f}; trend: {topic['trend']:.2f}; question accuracy: {topic['question_accuracy']:.2f}; practice hours: {topic['practice_hours']:.2f}",
			f"  Why: {', '.join(topic['reasons'])}",
			f"  Recommended support: {' '.join(topic['recommended_actions'])}",
		])
	lines.extend([
		"",
		"WHY?",
		"- Model-contribution reasons describe SHAP contributions to the prediction; they are not causal explanations.",
		*[f"- {reason}" for reason in report["reasons"]],
		"",
		"RECOMMENDED SUPPORT:",
		*[f"- {action}" for action in report["recommended_actions"]],
		"",
		"PROGRESS:",
		*[f"- {key}: {value:.3f}" for key, value in report["progress"].items()],
	])
	path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_rules(thresholds):
	"""Document every rule, threshold, mapping, and limitation."""
	lines = [
		"Personalized Learning Support Recommendation Rules",
		"===================================================",
		"Scope: early-data-only supportive recommendations; no student labeling or punishment.",
		"Input weeks: 1-6. Future weeks 7-10 and future-derived topic status are not used for recommendation priority.",
		"",
		"Student-level prediction:",
		"- Load the saved Random Forest model and use the saved 25-feature matrix.",
		"- predicted_learning_status is the model class with the highest predicted probability.",
		"- Predicted probabilities are reported for Low, Moderate, and High.",
		"",
		"Early topic thresholds (calculated over all student-topic early features):",
		f"- Lower early topic score: average_early_topic_score <= 25th percentile ({thresholds['early_score_p25']:.4f}). Adds 3 priority points.",
		f"- Declining early trend: early_topic_score_trend <= 25th percentile ({thresholds['trend_p25']:.4f}). Adds 2 priority points.",
		f"- Lower question accuracy: early_question_accuracy <= 25th percentile ({thresholds['accuracy_p25']:.4f}). Adds 2 priority points.",
		f"- Reduced practice: average_early_practice_hours <= 25th percentile ({thresholds['practice_hours_p25']:.4f}). Adds 1 priority point.",
		"- A topic is included when at least one rule triggers; the top five topics by score are reported.",
		"- Priority: High >= 5 points, Medium = 3-4, Support = 1-2, Monitor = 0.",
		"",
		"Support mapping:",
		"- Every actual topic has a topic-specific concept review and practice action.",
		"- Declining trend adds prerequisite review and guided practice.",
		"- Lower question accuracy adds question practice and mistake review.",
		"- Reduced practice adds a small, gradual practice-set suggestion.",
		"- Lower early score adds concise concept review before practice.",
		"",
		"SHAP use:",
		"- Per-student SHAP values for the predicted class provide model-contribution reasons.",
		"- SHAP contributions explain model behavior and do not establish causation.",
		"",
		"Limitations:",
		"- The dataset is synthetic and recommendations are prototype support prompts, not guaranteed interventions.",
		"- The validated future topic target and topic_summary are loaded for reference/validation only and are excluded from recommendation inputs to avoid leakage.",
		"- Human review and real learning-resource links are required before deployment.",
	]
	RULES_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_student_support(student_id):
	"""Return structured early-data-only support for one student."""
	early, topic, _, model, feature_columns, _ = _load_inputs()
	thresholds = _thresholds(topic)
	if student_id not in set(early["student_id"]):
		raise KeyError(f"Unknown student_id: {student_id}")
	reports, _ = _build_reports(early, topic, model, feature_columns, thresholds, [])
	return reports[student_id]


def main():
	early, topic, topic_summary, model, feature_columns, test_ids = _load_inputs()
	thresholds = _thresholds(topic)
	reports, recommendation_rows = _build_reports(early, topic, model, feature_columns, thresholds, test_ids)
	OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
	for student_id in test_ids[:5]:
		_write_report(reports[student_id], OUTPUT_DIR / f"{student_id}_support_report.txt")
	recommendation_rows.to_csv(CSV_PATH, index=False)
	_write_rules(thresholds)
	if set(recommendation_rows["topic"].unique()).difference(set(topic["topic"].unique())):
		raise ValueError("Recommendation contains a topic absent from the dataset")
	if set(feature_columns).intersection({"student_id", "academic_difficulty"}):
		raise ValueError("Recommendation model features contain ID or target")
	print("Recommendation engine created: YES")
	print(f"Students supported: {len(reports)}")
	print(f"Topics analyzed: {topic['topic'].nunique()}")
	print("Rules created: early score, trend, question accuracy, practice activity, SHAP reasons")
	print("Example reports: 5 test-set students")
	print(f"CSV saved: {CSV_PATH}")
	print("Leakage checks: PASSED (early features only; target/future fields excluded)")
	print("Recommendation stage complete: YES")


if __name__ == "__main__":
	main()
