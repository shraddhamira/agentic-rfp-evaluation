"""Create the local SQLite database and seed the example criteria."""

from pathlib import Path

from agentic_rfp.database import initialize_database, seed_default_criteria


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "rfp_evaluation.db"

initialize_database(DATABASE_PATH)
seed_default_criteria(DATABASE_PATH)
print(f"Initialized database at {DATABASE_PATH}")
