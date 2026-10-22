"""Validate and normalize model scorecards and collect warnings."""

from __future__ import annotations

import json
import math
from typing import Any


def validate_scorecard(raw: str | dict[str, Any], criteria: list[dict[str, Any]]) -> dict[str, Any]:
    """Normalize one model response against the authoritative active criteria.

    Missing, malformed, or duplicate criterion scores become zero. Out-of-range
    numeric scores are clipped. Every adjustment is reported in ``warnings``.
    """
    warnings: list[str] = []
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            payload = {}
            warnings.append(f"Response was not valid JSON: {exc.msg}.")
    elif isinstance(raw, dict):
        payload = raw
    else:
        payload = {}
        warnings.append("Response must be a JSON object.")

    if not isinstance(payload, dict):
        payload = {}
        warnings.append("Response JSON root must be an object.")

    entries = payload.get("criteria", [])
    if not isinstance(entries, list):
        entries = []
        warnings.append("Criteria result was not a list; all active criterion scores defaulted to zero.")

    by_id: dict[int, list[dict[str, Any]]] = {}
    known_ids = {c["criterion_id"] for c in criteria}
    for entry in entries:
        if not isinstance(entry, dict):
            warnings.append("Ignored a malformed criterion entry.")
            continue
        cid = entry.get("criterion_id")
        if isinstance(cid, bool) or not isinstance(cid, int):
            warnings.append("Ignored a criterion entry with a missing or invalid criterion_id.")
            continue
        if cid not in known_ids:
            warnings.append(f"Ignored result for unknown or inactive criterion {cid}.")
            continue
        by_id.setdefault(cid, []).append(entry)

    normalized: list[dict[str, Any]] = []
    for criterion in criteria:
        cid = criterion["criterion_id"]
        maximum = float(criterion["max_score"])
        weight = float(criterion["weight"])
        criterion_warnings: list[str] = []
        matches = by_id.get(cid, [])
        entry = matches[0] if len(matches) == 1 else {}
        if len(matches) > 1:
            criterion_warnings.append("Duplicate criterion entries found; score set to zero.")
        elif not matches:
            criterion_warnings.append("Criterion result missing; score set to zero.")

        raw_score = entry.get("score")
        score: float = 0.0
        if matches and len(matches) == 1:
            if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)) or not math.isfinite(float(raw_score)):
                criterion_warnings.append("Score missing or malformed; score set to zero.")
            else:
                score = float(raw_score)
                clipped = min(maximum, max(0.0, score))
                if clipped != score:
                    criterion_warnings.append(f"Score {score:g} clipped to the valid range 0-{maximum:g}.")
                score = clipped
            supplied_max = entry.get("max_score")
            if supplied_max is not None and (isinstance(supplied_max, bool) or not isinstance(supplied_max, (int, float)) or float(supplied_max) != maximum):
                criterion_warnings.append(f"Model maximum score ignored; database maximum is {maximum:g}.")

        justification = entry.get("justification", "") if isinstance(entry.get("justification", ""), str) else ""
        evidence = entry.get("evidence", "") if isinstance(entry.get("evidence", ""), str) else ""
        if not justification.strip():
            criterion_warnings.append("Justification missing.")
        if not evidence.strip():
            criterion_warnings.append("Evidence missing.")
        criterion_result = {
            "criterion_id": cid,
            "criterion_name": criterion["name"],
            "score": score,
            "max_score": maximum,
            "weight": weight,
            "justification": justification.strip(),
            "evidence": evidence.strip(),
            "warnings": criterion_warnings,
        }
        normalized.append(criterion_result)
        warnings.extend(f"{criterion['name']}: {warning}" for warning in criterion_warnings)

    risks = payload.get("risks", [])
    if not isinstance(risks, list) or any(not isinstance(risk, str) for risk in risks):
        risks = []
        warnings.append("Risks must be a list of text values; invalid risks were discarded.")
    summary = payload.get("overall_summary", "")
    if not isinstance(summary, str):
        summary = ""
        warnings.append("Overall summary was malformed and discarded.")

    return {
        "supplier_name": payload.get("supplier_name", "") if isinstance(payload.get("supplier_name", ""), str) else "",
        "criteria": normalized,
        "risks": risks,
        "overall_summary": summary,
        "warnings": warnings,
    }
