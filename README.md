# Explainable AI-Based Student Progress Prediction and Parental Monitoring System

## Project Objective

This project provides a Flask-based early-warning system for student progress. It analyzes academic performance and learning behavior data, predicts academic status, explains predictions, and presents focused, role-based dashboards for parents and students.

## Current Development Stage

The repository includes the trained prediction pipeline, Flask application, parent and student portals, and automated verification scripts. The available dataset is synthetic and intended for research and prototype work. Topic-level data and analysis artifacts remain available internally for existing ML workflows, but topic-specific analysis is not presented in the user-facing portals.

The synthetic data contains 500 anonymized students observed across 10 weeks, 5 subjects, and 25 topics, producing 125,000 student-week-topic records. It models correlated but noisy relationships between attendance, LMS activity, practice behavior, assessment results, and topic performance. Student-specific strengths, topic difficulty, and improving, stable, or declining trajectories create variation across learners.

Generate or regenerate the raw dataset with:

```powershell
python src/generate_dataset.py
```

The generator uses a fixed random seed (`20260915`) and writes `data/raw/student_learning_data.csv`. It does not create processed data or train a model.

### Academic Difficulty Target

The `academic_difficulty` target is generated after all observations are created and is based only on future performance: each student's mean `topic_score` across weeks 8-10 and the change in mean topic score from week 8 to week 10.

- `2 = High`: future mean score below 48, or future mean below 58 with a decline of at least 8 points.
- `1 = Moderate`: future mean below 68, or a decline of at least 10 points.
- `0 = Low`: all other future outcomes.

The target is repeated for that student's rows so it can be used as a student-level outcome. For an early-warning experiment, use only early observations such as weeks 1-7 as input features and keep `academic_difficulty` out of the feature set. Weeks 8-10 and any features calculated from them must be reserved for outcome construction or later evaluation to avoid future-information leakage.

## Planned ML Workflow

1. Collect and validate student academic and learning-behavior data.
2. Preprocess raw data and store prepared outputs separately.
3. Engineer features related to performance, engagement, and topic-level difficulty.
4. Train candidate models for early prediction of academic difficulty.
5. Evaluate model performance using suitable classification and regression metrics.
6. Analyze topic-level patterns to identify areas requiring attention.
7. Apply Explainable AI techniques to communicate the factors behind predictions.
8. Generate personalized learning support recommendations based on identified needs.
9. Present academic status, overall assessment performance, attendance, and simple learning suggestions through the Flask portals.

## Planned Technology Stack

- **Programming language:** Python
- **Data processing:** pandas, NumPy
- **Visualization:** Matplotlib, Seaborn
- **Machine learning:** scikit-learn
- **Experimentation:** Jupyter Notebook
- **Application layer:** Flask backend with HTML templates, JavaScript, and CSS
- **Future explainability layer:** Explainable AI methods selected after model design and evaluation

## Project Structure

- `data/`: Raw and processed datasets
- `models/`: Generated model artifacts
- `notebooks/`: Exploratory analysis and experiments
- `src/`: Data processing, modeling, topic analysis, explainability, and recommendation modules
- `app/`: Flask application and academic data services
- `templates/`: Parent and student portal pages
- `static/`: Portal CSS, JavaScript, and image assets
- `tests/`: Automated tests

The current raw dataset columns are: `student_id`, `week`, `subject`, `topic`, `attendance_percentage`, `lectures_attended`, `lectures_conducted`, `quiz_score`, `assignment_score`, `internal_assessment_score`, `lms_login_count`, `lms_resource_views`, `practice_sessions`, `practice_hours`, `questions_attempted`, `questions_correct`, `topic_score`, and `academic_difficulty`.

## Development Scope

The website is a read-only monitoring and learning-support prototype. The parent portal focuses on academic status, overall assessment performance, attendance, weekly progress, and brief support suggestions. The student portal focuses on academic progress, attendance, assessment performance, simple AI insights, and general study suggestions. Existing datasets, trained models, SHAP calculations, and API responses are retained.
