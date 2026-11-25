"""Flask application and REST API routes for AI-Academic-Support."""

import sys
from pathlib import Path
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services import (
    get_all_students,
    get_complete_student_dashboard,
    get_student_explanation,
    get_student_prediction,
    get_student_recommendations,
    get_student_topics,
)
from app.study_task_store import get_task_completions, set_task_completion

TEMPLATE_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"

app = Flask(
    __name__,
    template_folder=str(TEMPLATE_DIR),
    static_folder=str(STATIC_DIR),
)
app.secret_key = "ai-academic-support-secret-key-2026"
app.config["STUDY_TASK_DATABASE"] = str(
    Path(app.instance_path) / "study_task_completions.sqlite3"
)


# ---------------------------------------------------------------------------
# Authentication & Portal Routes
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    """Root redirect to unified login portal."""
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Unified login page with role-based access for Parent and Student."""
    if request.method == "GET":
        return render_template("login.html")

    # Handle form or JSON POST
    if request.is_json:
        data = request.get_json() or {}
        role = str(data.get("role", "")).strip().lower()
        student_id = str(data.get("student_id", "")).strip().upper()
        password = str(data.get("password", ""))
    else:
        role = str(request.form.get("role", "")).strip().lower()
        student_id = str(request.form.get("student_id", "")).strip().upper()
        password = str(request.form.get("password", ""))

    all_students = set(get_all_students())

    # Demo Authentication Rules:
    # 1. student_id must exist in the dataset (STU-0001 to STU-0500)
    # 2. Parent password: 'parent123'
    # 3. Student password: 'student123'
    if not student_id or student_id not in all_students:
        error_msg = f"Unknown student ID '{student_id}'. Please use an ID from STU-0001 to STU-0500 (e.g. STU-0004)."
        if request.is_json:
            return jsonify({"error": error_msg}), 401
        return render_template("login.html", error=error_msg), 401

    if role == "parent":
        if password != "parent123":
            error_msg = "Invalid password for Parent role. Demo password is: parent123"
            if request.is_json:
                return jsonify({"error": error_msg}), 401
            return render_template("login.html", error=error_msg), 401
        
        session["user"] = {"role": "parent", "student_id": student_id}
        redirect_target = f"/parent?student_id={student_id}"

    elif role == "student":
        if password != "student123":
            error_msg = "Invalid password for Student role. Demo password is: student123"
            if request.is_json:
                return jsonify({"error": error_msg}), 401
            return render_template("login.html", error=error_msg), 401
        
        session["user"] = {"role": "student", "student_id": student_id}
        redirect_target = f"/student?student_id={student_id}"

    else:
        error_msg = "Invalid role specified. Please select either Parent or Student."
        if request.is_json:
            return jsonify({"error": error_msg}), 400
        return render_template("login.html", error=error_msg), 400

    if request.is_json:
        return jsonify({
            "success": True,
            "role": role,
            "student_id": student_id,
            "redirect_url": redirect_target
        })
    return redirect(redirect_target)


@app.route("/logout", methods=["GET"])
def logout():
    """Clear session and return to login page."""
    session.clear()
    return redirect(url_for("login"))


def _get_parent_student_id() -> str:
    """Resolve active student ID from query parameter or session."""
    sid = request.args.get("student_id")
    if sid:
        return sid.strip().upper()
    user = session.get("user")
    if user and isinstance(user, dict) and user.get("student_id"):
        return user["student_id"]
    return "STU-0004"


@app.route("/parent", methods=["GET"])
@app.route("/parent/overview", methods=["GET"])
def parent_dashboard():
    """Render parent overview dashboard view."""
    sid = _get_parent_student_id()
    return render_template("parent_overview.html", active_page="overview", student_id=sid)


@app.route("/parent/performance", methods=["GET"])
def parent_performance():
    """Redirect the retired parent performance page to the single dashboard."""
    sid = _get_parent_student_id()
    return redirect(url_for("parent_dashboard", student_id=sid))


@app.route("/parent/topics", methods=["GET"])
def parent_topics():
    """Redirect: topic-wise analysis is removed from parent monitoring."""
    sid = _get_parent_student_id()
    return redirect(url_for("parent_dashboard", student_id=sid))


@app.route("/parent/ai-insights", methods=["GET"])
def parent_ai_insights():
    """Redirect the retired parent AI page to the single dashboard."""
    sid = _get_parent_student_id()
    return redirect(url_for("parent_dashboard", student_id=sid))


@app.route("/parent/support", methods=["GET"])
def parent_support():
    """Redirect: support guidance is unified in parent overview."""
    sid = _get_parent_student_id()
    return redirect(url_for("parent_dashboard", student_id=sid))


def _get_student_user_id() -> str:
    """Resolve active student ID from query parameter or session for student portal."""
    sid = request.args.get("student_id")
    if sid:
        return sid.strip().upper()
    user = session.get("user")
    if user and isinstance(user, dict) and user.get("student_id"):
        return user["student_id"]
    return "STU-0004"


@app.route("/student", methods=["GET"])
@app.route("/student/overview", methods=["GET"])
def student_dashboard():
    """Render student overview learning dashboard view."""
    sid = _get_student_user_id()
    return render_template("student_overview.html", active_page="overview", student_id=sid)


@app.route("/student/performance", methods=["GET"])
def student_performance_view():
    """Render student detailed learning performance view."""
    sid = _get_student_user_id()
    return render_template("student_performance.html", active_page="performance", student_id=sid)


@app.route("/student/topics", methods=["GET"])
def student_topics_view():
    """Redirect the retired topic progress page to the student overview."""
    sid = _get_student_user_id()
    return redirect(url_for("student_dashboard", student_id=sid))


@app.route("/student/ai-insights", methods=["GET"])
def student_ai_insights_view():
    """Render student AI learning insights view."""
    sid = _get_student_user_id()
    return render_template("student_ai_insights.html", active_page="ai-insights", student_id=sid)


@app.route("/student/recommendations", methods=["GET"])
def student_recommendations_view():
    """Render student personalized practice and recommendations view."""
    sid = _get_student_user_id()
    return render_template("student_recommendations.html", active_page="recommendations", student_id=sid)


# ---------------------------------------------------------------------------
# REST API Endpoints (Shared by Parent and Student Dashboards)
# ---------------------------------------------------------------------------
@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


@app.route("/api/students", methods=["GET"])
def list_students():
    """Return list of all anonymized student IDs."""
    students = get_all_students()
    return jsonify({"students": students})


@app.route("/api/student/<student_id>", methods=["GET"])
def student_dashboard_api(student_id: str):
    """Return complete dashboard payload for the specified student."""
    try:
        data = get_complete_student_dashboard(student_id)
        return jsonify(data)
    except (KeyError, ValueError):
        return jsonify({"error": "Student ID not found"}), 404


@app.route("/api/student/<student_id>/prediction", methods=["GET"])
def student_prediction(student_id: str):
    """Return only AI difficulty prediction information for the student."""
    try:
        data = get_student_prediction(student_id)
        return jsonify(data)
    except (KeyError, ValueError):
        return jsonify({"error": "Student ID not found"}), 404


@app.route("/api/student/<student_id>/topics", methods=["GET"])
def student_topics(student_id: str):
    """Return all 25 topics and attention priorities for the student."""
    try:
        data = get_student_topics(student_id)
        return jsonify(data)
    except (KeyError, ValueError):
        return jsonify({"error": "Student ID not found"}), 404


@app.route("/api/student/<student_id>/recommendations", methods=["GET"])
def student_recommendations(student_id: str):
    """Return personalized recommendations and guidance for the student."""
    try:
        data = get_student_recommendations(student_id)
        return jsonify(data)
    except (KeyError, ValueError):
        return jsonify({"error": "Student ID not found"}), 404


@app.route("/api/student/<student_id>/explanation", methods=["GET"])
def student_explanation(student_id: str):
    """Return parent-friendly SHAP explanation and factors for the student."""
    try:
        data = get_student_explanation(student_id)
        return jsonify(data)
    except (KeyError, ValueError):
        return jsonify({"error": "Student ID not found"}), 404


@app.route("/api/student/<student_id>/study-tasks", methods=["GET", "PUT"])
def student_study_tasks(student_id: str):
    """Read or update this student's task completion for the current study week."""
    sid = student_id.strip().upper()
    if sid not in set(get_all_students()):
        return jsonify({"error": "Student ID not found"}), 404

    database_path = app.config["STUDY_TASK_DATABASE"]
    if request.method == "GET":
        return jsonify(get_task_completions(database_path, sid))

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or set(payload) != {"task_id", "completed"}:
        return jsonify({
            "error": "Provide task_id and completed in the request body."
        }), 400
    try:
        result = set_task_completion(
            database_path,
            sid,
            payload["task_id"],
            payload["completed"],
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
