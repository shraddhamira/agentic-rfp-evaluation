"""Initialize SQLite and read/write evaluation data."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_CRITERIA = [
    {"criterion_id": 1, "name": "Technical Capability", "description": "Architecture, integrations, scalability, and technical fit.", "weight": 30.0, "max_score": 10.0},
    {"criterion_id": 2, "name": "Implementation Plan", "description": "Timeline, milestones, staffing, and risk plan.", "weight": 20.0, "max_score": 10.0},
    {"criterion_id": 3, "name": "Commercial Value", "description": "Pricing clarity, total cost, and assumptions.", "weight": 20.0, "max_score": 10.0},
    {"criterion_id": 4, "name": "Security & Compliance", "description": "Controls, certifications, privacy, and auditability.", "weight": 20.0, "max_score": 10.0},
    {"criterion_id": 5, "name": "Support & Experience", "description": "Support model, similar projects, and references.", "weight": 10.0, "max_score": 10.0},
]

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS evaluation_criteria (
    criterion_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    weight REAL NOT NULL CHECK (weight >= 0 AND weight <= 100),
    max_score REAL NOT NULL CHECK (max_score > 0),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);
CREATE TABLE IF NOT EXISTS rfp_runs (
    rfp_run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'evaluating', 'completed', 'failed')),
    warnings_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS rfp_run_criteria (
    rfp_run_id TEXT NOT NULL REFERENCES rfp_runs(rfp_run_id) ON DELETE CASCADE,
    criterion_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    weight REAL NOT NULL,
    max_score REAL NOT NULL,
    PRIMARY KEY (rfp_run_id, criterion_id)
);
CREATE TABLE IF NOT EXISTS supplier_results (
    rfp_run_id TEXT NOT NULL REFERENCES rfp_runs(rfp_run_id) ON DELETE CASCADE,
    supplier_name TEXT NOT NULL COLLATE NOCASE,
    submission_date TEXT NOT NULL,
    experience_rating REAL NOT NULL,
    absolute_score REAL NOT NULL,
    ppi REAL NOT NULL,
    final_rank INTEGER NOT NULL,
    result_json TEXT NOT NULL,
    PRIMARY KEY (rfp_run_id, supplier_name),
    UNIQUE (rfp_run_id, final_rank)
);
CREATE TABLE IF NOT EXISTS criterion_results (
    rfp_run_id TEXT NOT NULL,
    supplier_name TEXT NOT NULL COLLATE NOCASE,
    criterion_id INTEGER NOT NULL,
    score REAL NOT NULL,
    max_score REAL NOT NULL,
    weight REAL NOT NULL,
    benchmark_score REAL NOT NULL,
    gap REAL NOT NULL,
    relative_performance REAL NOT NULL,
    justification TEXT NOT NULL,
    evidence TEXT NOT NULL,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (rfp_run_id, supplier_name, criterion_id),
    FOREIGN KEY (rfp_run_id, supplier_name)
        REFERENCES supplier_results(rfp_run_id, supplier_name) ON DELETE CASCADE,
    FOREIGN KEY (rfp_run_id, criterion_id)
        REFERENCES rfp_run_criteria(rfp_run_id, criterion_id) ON DELETE CASCADE
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with foreign key checks enabled."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(db_path: str | Path) -> None:
    """Create the schema if it does not already exist."""
    with closing(connect(db_path)) as connection, connection:
        connection.executescript(SCHEMA)


def seed_default_criteria(db_path: str | Path) -> None:
    """Insert the brief's sample criteria only when the table is empty."""
    with closing(connect(db_path)) as connection, connection:
        count = connection.execute("SELECT COUNT(*) FROM evaluation_criteria").fetchone()[0]
        if count == 0:
            connection.executemany(
                """INSERT INTO evaluation_criteria
                   (criterion_id, name, description, weight, max_score, is_active)
                   VALUES (:criterion_id, :name, :description, :weight, :max_score, 1)""",
                DEFAULT_CRITERIA,
            )


def get_active_criteria(db_path: str | Path) -> list[dict[str, Any]]:
    """Return active criteria after enforcing the 100% weight rule."""
    with closing(connect(db_path)) as connection, connection:
        rows = connection.execute(
            """SELECT criterion_id, name, description, weight, max_score
               FROM evaluation_criteria WHERE is_active = 1 ORDER BY criterion_id"""
        ).fetchall()
    criteria = [dict(row) for row in rows]
    validate_criteria(criteria)
    return criteria


def get_run_criteria(db_path: str | Path, rfp_run_id: str) -> list[dict[str, Any]]:
    """Read the immutable criteria snapshot for an existing run."""
    with closing(connect(db_path)) as connection, connection:
        rows = connection.execute(
            """SELECT criterion_id, name, description, weight, max_score
               FROM rfp_run_criteria WHERE rfp_run_id = ? ORDER BY criterion_id""",
            (rfp_run_id,),
        ).fetchall()
    criteria = [dict(row) for row in rows]
    if not criteria:
        raise ValueError(f"No criteria snapshot found for RFP run {rfp_run_id}.")
    return validate_criteria(criteria)


def update_run_status(db_path: str | Path, rfp_run_id: str, status: str) -> None:
    """Move a run to evaluating or failed; completed writes use save_ranked_results."""
    if status not in {"evaluating", "failed"}:
        raise ValueError("Status must be 'evaluating' or 'failed'.")
    with closing(connect(db_path)) as connection, connection:
        cursor = connection.execute(
            "UPDATE rfp_runs SET status = ? WHERE rfp_run_id = ?",
            (status, rfp_run_id),
        )
        if cursor.rowcount != 1:
            raise ValueError(f"Unknown RFP run: {rfp_run_id}.")


def validate_criteria(criteria: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate criterion IDs, score ranges, and active weights; return a list."""
    items = list(criteria)
    if not items:
        raise ValueError("At least one active evaluation criterion is required.")
    ids: set[int] = set()
    total_weight = 0.0
    for item in items:
        cid = item.get("criterion_id")
        if isinstance(cid, bool) or not isinstance(cid, int) or cid in ids:
            raise ValueError("Criterion IDs must be unique integers.")
        ids.add(cid)
        weight = _finite_number(item.get("weight"), "criterion weight")
        maximum = _finite_number(item.get("max_score"), "criterion maximum score")
        if weight < 0 or weight > 100:
            raise ValueError(f"Weight for criterion {cid} must be between 0 and 100.")
        if maximum <= 0:
            raise ValueError(f"Maximum score for criterion {cid} must be greater than zero.")
        total_weight += weight
    if abs(total_weight - 100.0) > 1e-6:
        raise ValueError(f"Active criterion weights must total 100%; current total is {total_weight:g}%.")
    return items


def create_run(db_path: str | Path, rfp_run_id: str, criteria: list[dict[str, Any]]) -> None:
    """Create a pending run and snapshot its active criteria and weights."""
    items = validate_criteria(criteria)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(connect(db_path)) as connection, connection:
        connection.execute(
            "INSERT INTO rfp_runs (rfp_run_id, created_at, status) VALUES (?, ?, 'pending')",
            (rfp_run_id, created_at),
        )
        connection.executemany(
            """INSERT INTO rfp_run_criteria
               (rfp_run_id, criterion_id, name, description, weight, max_score)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [(rfp_run_id, c["criterion_id"], c["name"], c.get("description", ""), c["weight"], c["max_score"]) for c in items],
        )


def save_ranked_results(
    db_path: str | Path,
    rfp_run_id: str,
    suppliers: list[dict[str, Any]],
    warnings: list[str] | None = None,
) -> None:
    """Persist a complete ranked run and mark it completed atomically."""
    with closing(connect(db_path)) as connection, connection:
        run = connection.execute(
            "SELECT status FROM rfp_runs WHERE rfp_run_id = ?", (rfp_run_id,)
        ).fetchone()
        if run is None:
            raise ValueError(f"Unknown RFP run: {rfp_run_id}.")
        if run["status"] == "completed":
            raise ValueError(f"RFP run {rfp_run_id} is already completed.")
        run_criteria = connection.execute(
            "SELECT criterion_id, name, weight, max_score FROM rfp_run_criteria WHERE rfp_run_id = ?",
            (rfp_run_id,),
        ).fetchall()
        expected_ids = {row["criterion_id"] for row in run_criteria}
        if not suppliers:
            raise ValueError("Cannot complete a run without evaluated suppliers.")

        for supplier in suppliers:
            criteria = supplier.get("criteria", [])
            if {row.get("criterion_id") for row in criteria} != expected_ids:
                raise ValueError(f"Supplier {supplier.get('supplier_name', '(unknown)')} has incomplete criterion results.")
            encoded = json.dumps(supplier, ensure_ascii=False, allow_nan=False)
            connection.execute(
                """INSERT INTO supplier_results
                   (rfp_run_id, supplier_name, submission_date, experience_rating,
                    absolute_score, ppi, final_rank, result_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (rfp_run_id, supplier["supplier_name"], supplier["submission_date"],
                 supplier["experience_rating"], supplier["absolute_score"],
                 supplier["ppi"], supplier["final_rank"], encoded),
            )
            for result in criteria:
                connection.execute(
                    """INSERT INTO criterion_results
                       (rfp_run_id, supplier_name, criterion_id, score, max_score,
                        weight, benchmark_score, gap, relative_performance,
                        justification, evidence, warnings_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (rfp_run_id, supplier["supplier_name"], result["criterion_id"],
                     result["score"], result["max_score"], result["weight"],
                     result["benchmark_score"], result["gap"],
                     result["relative_performance"], result.get("justification", ""),
                     result.get("evidence", ""), json.dumps(result.get("warnings", []))),
                )
        connection.execute(
            "UPDATE rfp_runs SET status = 'completed', warnings_json = ? WHERE rfp_run_id = ?",
            (json.dumps(warnings or [], ensure_ascii=False), rfp_run_id),
        )


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number.")
    number = float(value)
    if not (float("-inf") < number < float("inf")):
        raise ValueError(f"{label} must be finite.")
    return number
