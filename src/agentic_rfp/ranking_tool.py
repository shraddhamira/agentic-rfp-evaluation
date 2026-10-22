"""Calculate deterministic scores, peer metrics, and supplier ordering."""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from .database import validate_criteria


def rank_suppliers(suppliers: list[dict[str, Any]], criteria: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Calculate metrics and return suppliers in final rank order.

    Each supplier must contain supplier_name, submission_date (ISO YYYY-MM-DD),
    experience_rating, and a validated ``criteria`` list from validate_scorecard.
    """
    criteria = validate_criteria(criteria)
    if not suppliers:
        return []

    names: set[str] = set()
    criterion_ids = {c["criterion_id"] for c in criteria}
    normalized_inputs: list[dict[str, Any]] = []
    for supplier in suppliers:
        name = supplier.get("supplier_name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Every supplier must have a non-empty name.")
        key = name.strip().casefold()
        if key in names:
            raise ValueError(f"Supplier names must be unique within a run: {name}.")
        names.add(key)
        try:
            submitted = date.fromisoformat(supplier["submission_date"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Supplier {name} must have a valid ISO submission_date (YYYY-MM-DD).") from exc
        experience = _number(supplier.get("experience_rating"), f"experience rating for {name}")
        scores = supplier.get("criteria")
        if not isinstance(scores, list):
            raise ValueError(f"Supplier {name} must have a validated criteria list.")
        by_id = {item.get("criterion_id"): item for item in scores if isinstance(item, dict)}
        if len(scores) != len(criterion_ids) or len(by_id) != len(scores) or set(by_id) != criterion_ids:
            raise ValueError(f"Supplier {name} must have exactly one validated result per active criterion.")
        for criterion in criteria:
            score = _number(by_id[criterion["criterion_id"]].get("score"), f"score for {name} / {criterion['name']}")
            if score < 0 or score > float(criterion["max_score"]):
                raise ValueError(f"Score for {name} / {criterion['name']} is outside its valid range.")
        normalized_inputs.append({**supplier, "supplier_name": name.strip(), "_submitted": submitted, "experience_rating": experience, "_by_id": by_id})

    benchmarks: dict[int, float] = {}
    for criterion in criteria:
        cid = criterion["criterion_id"]
        benchmarks[cid] = max(float(s["_by_id"][cid]["score"]) for s in normalized_inputs)

    ranked: list[dict[str, Any]] = []
    for supplier in normalized_inputs:
        details: list[dict[str, Any]] = []
        absolute_score = 0.0
        ppi = 0.0
        for criterion in criteria:
            cid = criterion["criterion_id"]
            score_row = supplier["_by_id"][cid]
            maximum = float(criterion["max_score"])
            weight = float(criterion["weight"])
            score = float(score_row["score"])
            benchmark = benchmarks[cid]
            normalized_score = score / maximum
            benchmark_normalized = benchmark / maximum
            gap = score - benchmark
            relative = 100.0 if benchmark == 0 else (score / benchmark) * 100.0
            absolute_score += normalized_score * weight
            ppi += relative * weight / 100.0
            details.append({
                **score_row,
                "score": score,
                "normalized_score": normalized_score,
                "benchmark_score": benchmark,
                "benchmark_normalized_score": benchmark_normalized,
                "gap": gap,
                "relative_performance": relative,
                "zero_benchmark_parity": benchmark == 0,
            })
        ranked.append({
            **{k: v for k, v in supplier.items() if not k.startswith("_")},
            "_submitted": supplier["_submitted"],
            "absolute_score": absolute_score,
            "ppi": ppi,
            "criteria": details,
        })

    ranked.sort(key=lambda s: (-s["ppi"], s["_submitted"], -s["experience_rating"], s["supplier_name"].casefold(), s["supplier_name"]))
    for rank, supplier in enumerate(ranked, start=1):
        supplier["final_rank"] = rank
        supplier.pop("_submitted", None)
        supplier.pop("_by_id", None)
    return ranked


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite.")
    return result
