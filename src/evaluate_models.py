"""Evaluate saved baseline classifiers for the early-prediction experiment."""

from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
	accuracy_score,
	classification_report,
	confusion_matrix,
	f1_score,
	precision_score,
	recall_score,
	roc_auc_score,
)

from train_models import DATA_PATH, MODELS_DIR, load_data, prepare_split


FIGURES_DIR = Path(__file__).resolve().parents[1] / "notebooks" / "figures"
MODEL_FILES = {
	"Logistic Regression": "logistic_regression.pkl",
	"Random Forest": "random_forest.pkl",
	"Support Vector Machine": "svm.pkl",
	"XGBoost": "xgboost.pkl",
}
CLASS_LABELS = ["Low", "Moderate", "High"]


def evaluate_saved_models():
	"""Evaluate all saved models on the untouched stratified test set."""
	data = load_data(DATA_PATH)
	X_train, X_test, y_train, y_test, ids_train, ids_test, feature_columns = prepare_split(data)
	saved_train_ids = set(pd.read_csv(MODELS_DIR / "train_students.csv")["student_id"])
	saved_test_ids = set(pd.read_csv(MODELS_DIR / "test_students.csv")["student_id"])
	if saved_train_ids != set(ids_train) or saved_test_ids != set(ids_test):
		raise ValueError("Saved split IDs do not reproduce the required split")
	if saved_train_ids.intersection(saved_test_ids):
		raise ValueError("Student leakage detected in saved split IDs")

	FIGURES_DIR.mkdir(parents=True, exist_ok=True)
	rows = []
	for name, filename in MODEL_FILES.items():
		model = joblib.load(MODELS_DIR / filename)
		artifact_stem = filename[:-4]
		predictions = model.predict(X_test)
		probabilities = model.predict_proba(X_test) if hasattr(model, "predict_proba") else None
		roc_auc = roc_auc_score(y_test, probabilities, multi_class="ovr", average="macro") if probabilities is not None else float("nan")
		rows.append({
			"Model": name,
			"Accuracy": accuracy_score(y_test, predictions),
			"Macro Precision": precision_score(y_test, predictions, average="macro", zero_division=0),
			"Macro Recall": recall_score(y_test, predictions, average="macro", zero_division=0),
			"Macro F1": f1_score(y_test, predictions, average="macro", zero_division=0),
			"Weighted F1": f1_score(y_test, predictions, average="weighted", zero_division=0),
			"ROC-AUC (OvR Macro)": roc_auc,
		})
		report = classification_report(
			y_test,
			predictions,
			labels=[0, 1, 2],
			target_names=CLASS_LABELS,
			zero_division=0,
		)
		(MODELS_DIR / (artifact_stem + "_classification_report.txt")).write_text(report, encoding="utf-8")
		matrix = confusion_matrix(y_test, predictions, labels=[0, 1, 2])
		plt.figure(figsize=(5, 4))
		sns.heatmap(matrix, annot=True, fmt="d", cmap="Blues", cbar=False,
					xticklabels=CLASS_LABELS, yticklabels=CLASS_LABELS)
		plt.title(name + " Confusion Matrix")
		plt.xlabel("Predicted label")
		plt.ylabel("True label")
		plt.tight_layout()
		plt.savefig(FIGURES_DIR / (artifact_stem + "_confusion_matrix.png"), dpi=150)
		plt.close()

	comparison = pd.DataFrame(rows).sort_values("Macro F1", ascending=False)
	comparison.to_csv(MODELS_DIR / "model_comparison.csv", index=False)
	plot_data = comparison.melt(
		id_vars="Model",
		value_vars=["Accuracy", "Macro Precision", "Macro Recall", "Macro F1", "Weighted F1"],
		var_name="Metric",
		value_name="Score",
	)
	plt.figure(figsize=(12, 6))
	sns.barplot(data=plot_data, x="Model", y="Score", hue="Metric")
	plt.ylim(0, 1)
	plt.xticks(rotation=15)
	plt.title("Baseline model performance comparison")
	plt.tight_layout()
	plt.savefig(FIGURES_DIR / "model_performance_comparison.png", dpi=150)
	plt.close()

	print("Evaluation results:")
	print(comparison.to_string(index=False))
	print("\\nStrongest overall baseline by Macro F1, with Macro Recall and Weighted F1 considered:")
	print(comparison.iloc[0].to_string())
	print("\\nLeakage checks: PASS")
	print("Results saved: models/model_comparison.csv and notebooks/figures/")
	print("ML experiment complete: YES")
	return comparison


if __name__ == "__main__":
	evaluate_saved_models()
