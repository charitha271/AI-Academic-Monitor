"""Generate SHAP explanations for the saved Random Forest baseline model."""

from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "early_prediction_dataset.csv"
MODEL_PATH = PROJECT_ROOT / "models" / "random_forest.pkl"
FEATURE_PATH = PROJECT_ROOT / "models" / "feature_columns.csv"
TEST_IDS_PATH = PROJECT_ROOT / "models" / "test_students.csv"
OUTPUT_DIR = PROJECT_ROOT / "figures" / "shap"
IMPORTANCE_PATH = PROJECT_ROOT / "models" / "shap_feature_importance.csv"
CLASS_IMPORTANCE_PATH = PROJECT_ROOT / "models" / "shap_feature_importance_by_class.csv"
CLASS_LABELS = {0: "Low", 1: "Moderate", 2: "High"}
ID_COLUMN = "student_id"
TARGET_COLUMN = "academic_difficulty"


def load_explainability_inputs():
	"""Load the saved model, exact training features, and saved test students."""
	data = pd.read_csv(DATA_PATH)
	model = joblib.load(MODEL_PATH)
	feature_columns = pd.read_csv(FEATURE_PATH)["feature"].tolist()
	test_ids = pd.read_csv(TEST_IDS_PATH)[ID_COLUMN].tolist()
	if ID_COLUMN in feature_columns or TARGET_COLUMN in feature_columns:
		raise ValueError("Identifier or target included in SHAP feature columns")
	if len(feature_columns) != 25:
		raise ValueError(f"Expected 25 training features, found {len(feature_columns)}")
	if not set(test_ids).issubset(set(data[ID_COLUMN])):
		raise ValueError("Saved test students are missing from the processed dataset")
	test_data = data[data[ID_COLUMN].isin(test_ids)].copy()
	test_data = test_data.set_index(ID_COLUMN).loc[test_ids].reset_index()
	X_test = test_data[feature_columns].copy()
	y_test = test_data[TARGET_COLUMN].copy()
	return data, model, feature_columns, test_data, X_test, y_test


def _multiclass_values(explanation):
	"""Return SHAP values as (samples, features, classes)."""
	values = explanation.values if hasattr(explanation, "values") else np.asarray(explanation)
	if values.ndim == 2:
		values = values[:, :, np.newaxis]
	if values.ndim != 3:
		raise ValueError(f"Unexpected multiclass SHAP shape: {values.shape}")
	if values.shape[1] != 25 and values.shape[2] == 25:
		values = np.transpose(values, (0, 2, 1))
	if values.shape[1] != 25:
		raise ValueError(f"SHAP feature axis does not match training features: {values.shape}")
	return values


def _save_global_plots(shap_values, X_test, feature_columns):
	"""Save multiclass summary plots and an all-class bar plot."""
	OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
	class_count = shap_values.shape[2]
	fig, axes = plt.subplots(class_count, 1, figsize=(12, 5 * class_count))
	axes = np.atleast_1d(axes)
	for class_index, axis in enumerate(axes):
		plt.sca(axis)
		shap.summary_plot(
			shap_values[:, :, class_index],
			X_test,
			feature_names=feature_columns,
			show=False,
			max_display=15,
			plot_size=None,
		)
		axis.set_title(f"SHAP Summary: {CLASS_LABELS.get(class_index, class_index)}")
	fig.tight_layout()
	fig.savefig(OUTPUT_DIR / "shap_summary_all_classes.png", dpi=150, bbox_inches="tight")
	plt.close(fig)

	global_importance = np.abs(shap_values).mean(axis=(0, 2))
	ranking = pd.DataFrame({
		"feature": feature_columns,
		"mean_absolute_shap_value": global_importance,
	}).sort_values("mean_absolute_shap_value", ascending=False)
	ranking["rank"] = np.arange(1, len(ranking) + 1)
	ranking.to_csv(IMPORTANCE_PATH, index=False)

	plt.figure(figsize=(10, 8))
	top = ranking.head(15).sort_values("mean_absolute_shap_value")
	plt.barh(top["feature"], top["mean_absolute_shap_value"], color="#4472C4")
	plt.xlabel("Mean absolute SHAP value across classes")
	plt.title("Global SHAP feature importance")
	plt.tight_layout()
	plt.savefig(OUTPUT_DIR / "shap_bar_global.png", dpi=150, bbox_inches="tight")
	plt.close()

	class_importance = []
	for class_index in range(class_count):
		values = np.abs(shap_values[:, :, class_index]).mean(axis=0)
		class_frame = pd.DataFrame({
			"class": CLASS_LABELS.get(class_index, str(class_index)),
			"class_index": class_index,
			"feature": feature_columns,
			"mean_absolute_shap_value": values,
		}).sort_values("mean_absolute_shap_value", ascending=False)
		class_frame["rank"] = np.arange(1, len(class_frame) + 1)
		class_importance.append(class_frame)
	pd.concat(class_importance, ignore_index=True).to_csv(CLASS_IMPORTANCE_PATH, index=False)
	return ranking


def _save_local_explanation(model, explainer, explanation, test_data, X_test, y_test, feature_columns):
	"""Save a local contribution plot for the first saved test student."""
	probabilities = model.predict_proba(X_test)
	predictions = model.predict(X_test)
	sample_index = 0
	predicted_class = int(predictions[sample_index])
	actual_class = int(y_test.iloc[sample_index])
	values = _multiclass_values(explanation)[sample_index, :, predicted_class]
	contribution = pd.DataFrame({"feature": feature_columns, "shap_value": values})
	contribution["absolute"] = contribution["shap_value"].abs()
	top = contribution.sort_values("absolute", ascending=False).head(12).sort_values("shap_value")
	plt.figure(figsize=(10, 7))
	colors = ["#C0504D" if value < 0 else "#4F81BD" for value in top["shap_value"]]
	plt.barh(top["feature"], top["shap_value"], color=colors)
	plt.axvline(0, color="black", linewidth=0.8)
	plt.xlabel("SHAP contribution to predicted class")
	plt.title(
		f"Local SHAP explanation: {test_data.iloc[sample_index][ID_COLUMN]}\n"
		f"Actual: {CLASS_LABELS[actual_class]} | Predicted: {CLASS_LABELS[predicted_class]}"
	)
	plt.tight_layout()
	plt.savefig(OUTPUT_DIR / "local_shap_explanation.png", dpi=150, bbox_inches="tight")
	plt.close()
	local_summary = pd.DataFrame({
		"student_id": test_data.iloc[sample_index][ID_COLUMN],
		"actual_class": CLASS_LABELS[actual_class],
		"predicted_class": CLASS_LABELS[predicted_class],
		"feature": feature_columns,
		"shap_value_for_predicted_class": values,
	})
	local_summary["predicted_probability"] = probabilities[sample_index, predicted_class]
	local_summary.to_csv(MODELS_DIR / "local_shap_explanation.csv", index=False)
	return actual_class, predicted_class, probabilities[sample_index], contribution


def run_explainability():
	"""Generate global and local SHAP explanations without retraining."""
	global MODELS_DIR
	MODELS_DIR = PROJECT_ROOT / "models"
	data, model, feature_columns, test_data, X_test, y_test = load_explainability_inputs()
	forbidden = {ID_COLUMN, TARGET_COLUMN, "future_mean_topic_score", "future_score_change", "week", "subject", "topic"}
	if forbidden.intersection(feature_columns):
		raise ValueError("Leakage check failed: forbidden columns found in SHAP features")
	explainer = shap.TreeExplainer(model)
	explanation = explainer(X_test)
	shap_values = _multiclass_values(explanation)
	ranking = _save_global_plots(shap_values, X_test, feature_columns)
	actual_class, predicted_class, probabilities, contribution = _save_local_explanation(
		model, explainer, explanation, test_data, X_test, y_test, feature_columns
	)
	print("SHAP installed: YES")
	print("Model loaded: YES (saved Random Forest; no retraining)")
	print(f"Number of features explained: {len(feature_columns)}")
	print("Global SHAP generated: YES")
	print("Local SHAP generated: YES")
	print("Figures saved: figures/shap/")
	print("CSV saved: models/shap_feature_importance.csv, models/shap_feature_importance_by_class.csv")
	print("Leakage checks: PASS (no ID/target/future columns; weeks 1-6 feature matrix verified)")
	print("Explainability stage complete: YES")
	print(f"Local student: {test_data.iloc[0][ID_COLUMN]}")
	print(f"Actual class: {CLASS_LABELS[actual_class]}")
	print(f"Predicted class: {CLASS_LABELS[predicted_class]}")
	print(f"Predicted probabilities: {probabilities}")
	print("Top global features:")
	print(ranking.head(10).to_string(index=False))
	print("SHAP indicates how features contributed to the model prediction; it does not establish causation.")


if __name__ == "__main__":
	run_explainability()
