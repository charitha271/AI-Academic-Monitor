"""Train baseline classifiers for the early academic-difficulty experiment."""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from xgboost import XGBClassifier


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "early_prediction_dataset.csv"
MODELS_DIR = PROJECT_ROOT / "models"
RANDOM_STATE = 42
TEST_SIZE = 0.20
TARGET_COLUMN = "academic_difficulty"
ID_COLUMN = "student_id"


def load_data(path=DATA_PATH):
	"""Load the processed one-row-per-student dataset."""
	return pd.read_csv(path)


def prepare_split(data):
	"""Select X/y and create the required stratified student-level split."""
	if data[ID_COLUMN].duplicated().any():
		raise ValueError("Processed dataset contains duplicate students")
	if data.isna().any().any():
		raise ValueError("Processed dataset contains missing values")

	feature_columns = [column for column in data.columns if column not in {ID_COLUMN, TARGET_COLUMN}]
	if ID_COLUMN in feature_columns or TARGET_COLUMN in feature_columns:
		raise ValueError("Identifier or target was included in model features")
	forbidden_future_columns = {"future_mean_topic_score", "future_score_change", "week", "subject", "topic"}
	if forbidden_future_columns.intersection(feature_columns):
		raise ValueError("Future or raw repeated-record columns were included in model features")

	X = data[feature_columns].copy()
	y = data[TARGET_COLUMN].copy()
	student_ids = data[ID_COLUMN].copy()
	X_train, X_test, y_train, y_test, ids_train, ids_test = train_test_split(
		X,
		y,
		student_ids,
		test_size=TEST_SIZE,
		random_state=RANDOM_STATE,
		stratify=y,
	)
	train_students = set(ids_train)
	test_students = set(ids_test)
	if train_students.intersection(test_students):
		raise ValueError("Student leakage detected between train and test")
	return X_train, X_test, y_train, y_test, ids_train, ids_test, feature_columns


def build_models(class_weights):
	"""Return reasonable untuned baseline models."""
	return {
		"Logistic Regression": Pipeline([
			("scaler", StandardScaler()),
			("classifier", LogisticRegression(
				max_iter=2000,
				class_weight=class_weights,
				random_state=RANDOM_STATE,
			)),
		]),
		"Random Forest": RandomForestClassifier(
			n_estimators=300,
			class_weight=class_weights,
			random_state=RANDOM_STATE,
			n_jobs=-1,
		),
		"Support Vector Machine": Pipeline([
			("scaler", StandardScaler()),
			("classifier", SVC(
				probability=True,
				class_weight=class_weights,
				random_state=RANDOM_STATE,
			)),
		]),
		"XGBoost": XGBClassifier(
			objective="multi:softprob",
			num_class=3,
			n_estimators=250,
			max_depth=4,
			learning_rate=0.05,
			subsample=0.85,
			colsample_bytree=0.85,
			eval_metric="mlogloss",
			random_state=RANDOM_STATE,
			n_jobs=-1,
		),
	}


def train_and_save():
	"""Train all baselines and persist models, split IDs, and metadata."""
	data = load_data()
	X_train, X_test, y_train, y_test, ids_train, ids_test, feature_columns = prepare_split(data)
	class_weights = (
		y_train.value_counts().sum() / (y_train.nunique() * y_train.value_counts())
	).to_dict()
	models = build_models(class_weights)
	MODELS_DIR.mkdir(parents=True, exist_ok=True)

	# XGBoost receives equivalent inverse-frequency sample weights because its
	# multiclass estimator does not use sklearn's class_weight parameter.
	sample_weights = y_train.map(class_weights).to_numpy()
	trained_models = {}
	for name, model in models.items():
		if name == "XGBoost":
			model.fit(X_train, y_train, sample_weight=sample_weights)
		else:
			model.fit(X_train, y_train)
		trained_models[name] = model

	artifact_names = {
		"Logistic Regression": "logistic_regression.pkl",
		"Random Forest": "random_forest.pkl",
		"Support Vector Machine": "svm.pkl",
		"XGBoost": "xgboost.pkl",
	}
	for name, model in trained_models.items():
		joblib.dump(model, MODELS_DIR / artifact_names[name])

	pd.DataFrame({ID_COLUMN: ids_train}).to_csv(MODELS_DIR / "train_students.csv", index=False)
	pd.DataFrame({ID_COLUMN: ids_test}).to_csv(MODELS_DIR / "test_students.csv", index=False)
	pd.DataFrame({"feature": feature_columns}).to_csv(MODELS_DIR / "feature_columns.csv", index=False)
	pd.DataFrame({"setting": [
		"data=early_prediction_dataset.csv",
		"input_weeks=1-6; target_weeks=7-10",
		"test_size=0.20",
		"random_state=42",
		"stratify=academic_difficulty",
		f"class_weights={class_weights}",
		"xgboost_objective=multi:softprob; num_class=3; sample_weight=inverse_frequency",
		"models=logistic_regression, random_forest, svm, xgboost",
	]}).to_csv(MODELS_DIR / "experiment_settings.csv", index=False)

	print(f"Dataset shape: {data.shape}")
	print(f"Number of features: {len(feature_columns)}")
	print(f"Training students: {len(ids_train)}")
	print(f"Testing students: {len(ids_test)}")
	print(f"Training class distribution: {y_train.value_counts().sort_index().to_dict()}")
	print(f"Testing class distribution: {y_test.value_counts().sort_index().to_dict()}")
	print(f"Models trained: {', '.join(trained_models)}")
	print("Leakage checks: PASS (student IDs excluded; disjoint split; early features only)")
	print("Results saved: models/*.pkl, train_students.csv, test_students.csv")
	print("ML experiment complete: training stage YES")
	return trained_models, X_test, y_test, ids_train, ids_test, feature_columns


if __name__ == "__main__":
	train_and_save()
