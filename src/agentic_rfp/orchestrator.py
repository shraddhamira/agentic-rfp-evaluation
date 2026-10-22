"""Coordinate proposal extraction, evaluation, validation, ranking, and saving."""

from __future__ import annotations

import uuid
import logging
from pathlib import Path
from typing import Any

from .database import (
    create_run,
    get_active_criteria,
    get_run_criteria,
    save_ranked_results,
    update_run_status,
)
from .document_tool import extract_pdf_text
from .evaluation_agent import JsonLLMClient, evaluate_supplier
from .ranking_tool import rank_suppliers
from .validation_tool import validate_scorecard


logger = logging.getLogger(__name__)


def run_evaluation(
    db_path: str | Path,
    suppliers: list[dict[str, Any]],
    llm_client: JsonLLMClient,
    rfp_run_id: str | None = None,
) -> dict[str, Any]:
    """Run one batch. Supplier rows need name/date/rating and PDF bytes or path.

    This orchestrator routes work to the document tool and Evaluation Agent, then
    calls deterministic validation/ranking tools and persists the completed run.
    API credentials stay inside the injected client and are never put in run data.
    """
    run_id = rfp_run_id or str(uuid.uuid4())
    warnings: list[str] = []
    run_created = False
    try:
        if not suppliers:
            raise ValueError("Upload at least one supplier proposal before starting a run.")
        logger.info("Evaluation run started: run_id=%s supplier_count=%d", run_id, len(suppliers))
        active_criteria = get_active_criteria(db_path)
        create_run(db_path, run_id, active_criteria)
        run_created = True
        update_run_status(db_path, run_id, "evaluating")
        # Reload the immutable snapshot so all agents use the criteria for this run.
        run_criteria = get_run_criteria(db_path, run_id)
        validated_suppliers: list[dict[str, Any]] = []

        for supplier_index, supplier in enumerate(suppliers, start=1):
            name = supplier.get("supplier_name")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Every supplier needs a name.")
            if "pdf_bytes" in supplier:
                pdf_source = supplier["pdf_bytes"]
            elif "pdf_path" in supplier:
                pdf_source = supplier["pdf_path"]
            else:
                raise ValueError(f"Supplier {name} has no PDF bytes or pdf_path.")

            logger.info("Supplier %d/%d: PDF extraction started", supplier_index, len(suppliers))
            extracted = extract_pdf_text(pdf_source)
            logger.info(
                "Supplier %d/%d: PDF extraction completed (characters=%d)",
                supplier_index, len(suppliers), len(extracted["text"]),
            )
            warnings.extend(f"{name}: {warning}" for warning in extracted["warnings"])
            logger.info("Supplier %d/%d: evaluation agent started", supplier_index, len(suppliers))
            raw_scorecard, prompt_warnings = evaluate_supplier(
                llm_client, name.strip(), run_criteria, extracted["text"]
            )
            warnings.extend(f"{name}: {warning}" for warning in prompt_warnings)
            scorecard = validate_scorecard(raw_scorecard, run_criteria)
            logger.info("Supplier %d/%d: response validated", supplier_index, len(suppliers))
            warnings.extend(f"{name}: {warning}" for warning in scorecard["warnings"])
            validated_suppliers.append({
                "supplier_name": name.strip(),
                "submission_date": supplier.get("submission_date"),
                "experience_rating": supplier.get("experience_rating"),
                "criteria": scorecard["criteria"],
                "risks": scorecard["risks"],
                "overall_summary": scorecard["overall_summary"],
                "warnings": scorecard["warnings"],
            })

        ranked = rank_suppliers(validated_suppliers, run_criteria)
        save_ranked_results(db_path, run_id, ranked, warnings)
        logger.info("Evaluation run completed: run_id=%s supplier_count=%d", run_id, len(ranked))
        return {"rfp_run_id": run_id, "status": "completed", "warnings": warnings, "suppliers": ranked}
    except Exception:
        logger.exception("Evaluation run failed: run_id=%s", run_id)
        if run_created:
            try:
                update_run_status(db_path, run_id, "failed")
            except Exception:
                pass
        raise
    finally:
        clear_credentials = getattr(llm_client, "clear_credentials", None)
        if callable(clear_credentials):
            clear_credentials()
