"""Persistent completion storage for the student's current weekly study plan."""

import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict


TASK_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,159}$")


def current_week_start() -> str:
    """Return the ISO date for the Monday of the current local week."""
    today = date.today()
    return (today.fromordinal(today.toordinal() - today.weekday())).isoformat()


def get_task_completions(database_path: str, student_id: str) -> Dict[str, object]:
    week_start = current_week_start()
    connection = _connect(database_path)
    try:
        rows = connection.execute(
            """
            SELECT task_id, completed
            FROM study_task_completion
            WHERE student_id = ? AND week_start = ?
            """,
            (student_id, week_start),
        ).fetchall()
    finally:
        connection.close()
    return {
        "student_id": student_id,
        "week_start": week_start,
        "completions": {task_id: bool(completed) for task_id, completed in rows},
    }


def set_task_completion(
    database_path: str, student_id: str, task_id: str, completed: bool
) -> Dict[str, object]:
    if not isinstance(task_id, str) or not TASK_ID_PATTERN.fullmatch(task_id):
        raise ValueError("Invalid study task ID.")
    if not isinstance(completed, bool):
        raise ValueError("Task completion must be a boolean.")

    week_start = current_week_start()
    updated_at = datetime.now(timezone.utc).isoformat()
    connection = _connect(database_path)
    try:
        connection.execute(
            """
            INSERT INTO study_task_completion
                (student_id, week_start, task_id, completed, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(student_id, week_start, task_id)
            DO UPDATE SET completed = excluded.completed, updated_at = excluded.updated_at
            """,
            (student_id, week_start, task_id, int(completed), updated_at),
        )
        connection.commit()
    finally:
        connection.close()
    return {
        "student_id": student_id,
        "week_start": week_start,
        "task_id": task_id,
        "completed": completed,
    }


def _connect(database_path: str) -> sqlite3.Connection:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=10)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS study_task_completion (
                student_id TEXT NOT NULL,
                week_start TEXT NOT NULL,
                task_id TEXT NOT NULL,
                completed INTEGER NOT NULL CHECK (completed IN (0, 1)),
                updated_at TEXT NOT NULL,
                PRIMARY KEY (student_id, week_start, task_id)
            )
            """
        )
    except sqlite3.Error:
        connection.close()
        raise
    return connection
