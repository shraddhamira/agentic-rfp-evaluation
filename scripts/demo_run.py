"""Run a reproducible offline demo of the Orchestrator and validation behavior.

This uses a deterministic stand-in for an LLM; it makes no external API calls.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agentic_rfp.database import initialize_database, seed_default_criteria
from agentic_rfp.orchestrator import run_evaluation


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "rfp_evaluation.db"
PDF_DIR = ROOT / "sample_proposals"
EXPORT_PATH = ROOT / "sample_run.json"


class DemoLLM:
    """Deterministic fake that supplies known scorecards for the sample PDFs."""

    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        request = json.loads(user_prompt)
        name = request["supplier_name"]
        scorecards: dict[str, dict[str, Any]] = {
            "Apex Systems": {
                "criteria": [
                    {"criterion_id": 1, "score": 9, "max_score": 10, "justification": "An API-first design and message queue are described.", "evidence": "A message queue will isolate integrations from user-facing transactions."},
                    {"criterion_id": 2, "score": 7, "max_score": 10, "justification": "The proposal gives phased milestones over 14 months.", "evidence": "The proposed schedule is 14 months from kickoff"},
                    {"criterion_id": 3, "score": 6, "max_score": 10, "justification": "The proposal is detailed but has a higher implementation price.", "evidence": "The implementation total is $2.13 million."},
                    {"criterion_id": 4, "score": 9, "max_score": 10, "justification": "A control matrix and independent assurance are identified.", "evidence": "We will provide a control matrix mapped to NMS requirements."},
                    {"criterion_id": 5, "score": 8, "max_score": 10, "justification": "Critical support includes rapid acknowledgement.", "evidence": "24x7 priority-one intake, a 30-minute acknowledgement target for critical incidents."},
                ],
                "risks": ["Interface approvals may affect schedule."],
                "overall_summary": "Strong technical and security proposal at a higher cost.",
            },
            "BrightPath Tech": {
                "criteria": [
                    {"criterion_id": 1, "score": 7, "max_score": 10, "justification": "The Hub offers standard forms, queues, and dashboards.", "evidence": "BrightPath Hub provides web forms, email notifications, queues, and basic dashboards."},
                    {"criterion_id": 2, "score": "fast", "max_score": 10, "justification": "The schedule is short but detailed exit criteria are limited.", "evidence": "BrightPath targets a nine-month delivery."},
                    {"criterion_id": 3, "score": 10, "max_score": 10, "justification": "The implementation price is the lowest in this proposal set.", "evidence": "The fixed implementation price is $900,000."},
                    {"criterion_id": 4, "score": 12, "max_score": 10, "justification": "Basic encryption is mentioned but assurance evidence is absent.", "evidence": "The proposal states that data is encrypted in transit and at rest."},
                    # Criterion 5 intentionally omitted to demonstrate defaulting and warnings.
                ],
                "risks": ["Security assurance and support targets remain unspecified."],
                "overall_summary": "Low price and fast target schedule; proposal leaves assurance and experience details open.",
            },
            "NexaWorks": {
                "criteria": [
                    {"criterion_id": 1, "score": 8, "max_score": 10, "justification": "The proposal combines accessible intake with an integration layer.", "evidence": "The solution combines a configurable case platform, accessible resident forms, a staff workspace, and an integration layer."},
                    {"criterion_id": 2, "score": 9, "max_score": 10, "justification": "The 12-month plan has clear phases and exit evidence.", "evidence": "We recommend a 12-month delivery with a service-design phase, working prototypes, staged integration, and a supported pilot before wider rollout."},
                    {"criterion_id": 3, "score": 8, "max_score": 10, "justification": "The fixed implementation total and optional services are separated.", "evidence": "The fixed implementation total is $1.50 million."},
                    {"criterion_id": 4, "score": 8, "max_score": 10, "justification": "The proposal identifies controls and partner assurance for review.", "evidence": "The hosting partner's SOC 2 Type II summary and data-processing terms are available for review."},
                    {"criterion_id": 5, "score": 9, "max_score": 10, "justification": "Stabilization and optional managed support are described.", "evidence": "NexaWorks proposes a 90-day stabilization period with daily triage during launch week."},
                ],
                "risks": ["Final hosting region and service priorities need confirmation."],
                "overall_summary": "Balanced proposal with a strong implementation and support plan.",
            },
            "Orbit Digital": {
                "criteria": [
                    {"criterion_id": 1, "score": 7, "max_score": 10, "justification": "The core platform scope is clear while integration patterns remain open.", "evidence": "OrbitOne includes configurable case records, a resident-facing request form, workflow queues, and management dashboards."},
                    {"criterion_id": 2, "score": 7, "max_score": 10, "justification": "The 11-month target is provided, but detailed exit criteria are deferred.", "evidence": "The 11-month target is based on Orbit's prior program experience."},
                    {"criterion_id": 3, "score": 7, "max_score": 10, "justification": "The estimate is mid-range but includes allowances to confirm.", "evidence": "The stated implementation estimate is $1.66 million."},
                    {"criterion_id": 4, "score": 7, "max_score": 10, "justification": "Common controls are stated; region and assurance details remain open.", "evidence": "Orbit states that OrbitOne supports encryption, role permissions, audit history, and configurable retention."},
                    {"criterion_id": 5, "score": 9, "max_score": 10, "justification": "The proposal offers extensive public-service experience and references.", "evidence": "Orbit reports 15 years in enterprise delivery and lists a senior team with experience in municipal licensing, transit operations, and public-benefit casework."},
                ],
                "risks": ["Integration inventory and service targets require clarification."],
                "overall_summary": "Strong experience and references, with integration and service details to resolve.",
            },
        }
        scorecard = scorecards[name]
        def normalize(value: str) -> str:
            return " ".join(re.sub(r"[^\w\s]", " ", value.casefold()).split())

        document_text = normalize(request["proposal_text_with_page_markers"])
        for criterion in scorecard["criteria"]:
            evidence = normalize(criterion["evidence"])
            if evidence and evidence not in document_text:
                raise ValueError(f"Demo evidence for {name} / criterion {criterion['criterion_id']} is not present in the extracted proposal text.")
        return json.dumps({"supplier_name": name, **scorecard})


def main() -> None:
    initialize_database(DB_PATH)
    seed_default_criteria(DB_PATH)
    suppliers = [
        {"supplier_name": "Apex Systems", "submission_date": "2026-10-18", "experience_rating": 7, "pdf_path": PDF_DIR / "apex_systems.pdf"},
        {"supplier_name": "BrightPath Tech", "submission_date": "2026-10-20", "experience_rating": 3, "pdf_path": PDF_DIR / "brightpath_tech.pdf"},
        {"supplier_name": "NexaWorks", "submission_date": "2026-10-17", "experience_rating": 8, "pdf_path": PDF_DIR / "nexaworks.pdf"},
        {"supplier_name": "Orbit Digital", "submission_date": "2026-10-19", "experience_rating": 9, "pdf_path": PDF_DIR / "orbit_digital.pdf"},
    ]
    result = run_evaluation(DB_PATH, suppliers, DemoLLM())
    export = {
        **result,
        "demo_mode": "Deterministic mock LLM; no external provider was called.",
        "validation_case": "BrightPath returned a malformed score, an out-of-range score, and omitted a criterion. The validator defaulted or clipped those values and recorded warnings.",
    }
    EXPORT_PATH.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Completed demo run: {result['rfp_run_id']}")
    print("Leaderboard:")
    for supplier in result["suppliers"]:
        print(f"  {supplier['final_rank']}. {supplier['supplier_name']}: absolute={supplier['absolute_score']:.2f}, PPI={supplier['ppi']:.2f}")
    print("BrightPath validation warnings:")
    brightpath = next(s for s in result["suppliers"] if s["supplier_name"] == "BrightPath Tech")
    for warning in brightpath["warnings"]:
        print(f"  - {warning}")
    print(f"JSON export: {EXPORT_PATH}")


if __name__ == "__main__":
    main()
