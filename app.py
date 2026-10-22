"""Streamlit interface for evidence-backed supplier proposal evaluation."""

from __future__ import annotations

import json
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import streamlit as st

from agentic_rfp.database import get_active_criteria, initialize_database, seed_default_criteria
from agentic_rfp.evaluation_agent import OpenAICompatibleClient
from agentic_rfp.orchestrator import run_evaluation


PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_PATH = PROJECT_ROOT / "data" / "rfp_evaluation.db"
LOG_PATH = Path(os.environ.get("AGENTIC_RFP_LOG_PATH", PROJECT_ROOT / "data" / "agentic_rfp.log"))
MODEL_OPTIONS = [
    "openrouter/free",
    "openai/gpt-6-luna",
    "openai/gpt-5.6-luna",
    "openai/gpt-5.4-mini",
    "openai/gpt-4.1-mini",
]
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Logs show pipeline progress and provider diagnostics, never API keys or PDF text.
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
app_logger = logging.getLogger("agentic_rfp")
if not app_logger.handlers:
    app_logger.setLevel(logging.INFO)
    log_format = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(log_format)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    app_logger.addHandler(file_handler)
    app_logger.addHandler(console_handler)
app_logger.propagate = False

st.set_page_config(page_title="Agentic RFP Evaluation", page_icon="📋", layout="wide")

# Clear sensitive/form inputs only after a successful run. Failed runs keep the
# user's entries in this Streamlit session so they can fix the issue and retry.
if st.session_state.pop("_clear_evaluation_inputs", False):
    input_prefixes = ("supplier_name_", "submission_date_", "experience_rating_")
    input_keys = [
        key for key in st.session_state
        if key in {"proposal_uploads", "llm_api_key", "llm_model", "llm_base_url"}
        or key.startswith(input_prefixes)
    ]
    for key in input_keys:
        del st.session_state[key]

# Migrate the previous OpenAI defaults to the OpenRouter equivalents while
# leaving any custom endpoint/model choice untouched.
if st.session_state.get("llm_base_url") == "https://api.openai.com/v1":
    st.session_state["llm_base_url"] = OPENROUTER_BASE_URL
old_model = st.session_state.get("llm_model")
if old_model in {"openai/gpt-5.6-luna", "gpt-5.6-luna"}:
    st.session_state["llm_model"] = "openrouter/free"
elif old_model in {option.split("/", 1)[1] for option in MODEL_OPTIONS if option.startswith("openai/")}:
    st.session_state["llm_model"] = f"openai/{old_model}"

st.title("Agentic RFP Evaluation")
st.caption("Evidence-backed supplier scoring, peer comparison, and deterministic ranking")

try:
    initialize_database(DATABASE_PATH)
    seed_default_criteria(DATABASE_PATH)
    active_criteria = get_active_criteria(DATABASE_PATH)
except Exception as exc:
    st.error(f"Could not load evaluation criteria: {exc}")
    st.stop()

st.header("Active evaluation criteria")
st.dataframe(
    [
        {
            "Criterion": criterion["name"],
            "Description": criterion["description"],
            "Weight": f"{criterion['weight']:g}%",
            "Maximum score": criterion["max_score"],
        }
        for criterion in active_criteria
    ],
    hide_index=True,
    use_container_width=True,
)

st.header("Evaluate supplier proposals")
uploaded_files = st.file_uploader(
    "Upload one or more supplier proposal PDFs",
    type=["pdf"],
    accept_multiple_files=True,
    key="proposal_uploads",
    help="Scanned PDFs without an embedded text layer need OCR before they can be evaluated.",
)

if uploaded_files:
    st.caption(f"{len(uploaded_files)} PDF(s) ready. Enter metadata for each supplier and the LLM connection details below.")
else:
    st.info("Upload proposal PDFs to enter supplier details and start an evaluation.")

with st.form("evaluation_form", clear_on_submit=False):
    supplier_metadata: list[dict[str, Any]] = []
    if uploaded_files:
        st.subheader("Supplier details")
        for index, uploaded_file in enumerate(uploaded_files):
            default_name = Path(uploaded_file.name).stem.replace("_", " ").replace("-", " ").strip()
            with st.expander(f"{uploaded_file.name}", expanded=True):
                name = st.text_input("Supplier name", value=default_name, key=f"supplier_name_{index}")
                columns = st.columns(2)
                submitted_on = columns[0].date_input(
                    "Submission date", value=date.today(), key=f"submission_date_{index}"
                )
                experience = columns[1].number_input(
                    "Historical experience rating",
                    min_value=0.0,
                    value=0.0,
                    step=0.5,
                    help="Enter a non-negative numeric rating. Higher values rank first only when PPI and submission date are tied.",
                    key=f"experience_rating_{index}",
                )
                supplier_metadata.append({
                    "supplier_name": name.strip(),
                    "submission_date": submitted_on.isoformat(),
                    "experience_rating": float(experience),
                    "pdf_bytes": uploaded_file.getvalue(),
                })

    st.subheader("LLM connection")
    st.caption("The key is sent only to the configured endpoint. It is never saved to the database or a file. Inputs stay in this browser session if evaluation fails, so you can correct the settings and retry; after a successful run, the form inputs are cleared.")
    api_key = st.text_input("LLM API key", type="password", key="llm_api_key")
    model = st.selectbox(
        "Model name",
        options=MODEL_OPTIONS,
        index=MODEL_OPTIONS.index("openrouter/free"),
        key="llm_model",
        help="openrouter/free routes to an available free model. The other four choices use OpenAI models through OpenRouter.",
    )
    base_url = st.text_input(
        "OpenRouter API base URL",
        value=OPENROUTER_BASE_URL,
        help="OpenRouter's OpenAI-compatible Chat Completions endpoint.",
        key="llm_base_url",
    )
    submitted = st.form_submit_button(
        "Evaluate suppliers",
        type="primary",
        disabled=not bool(uploaded_files),
        use_container_width=True,
    )

evaluation_failed = False
if submitted:
    if not api_key.strip():
        st.error("Enter an LLM API key to run the evaluation.")
    elif not model.strip():
        st.error("Enter the model name configured for your LLM provider.")
    elif any(not supplier["supplier_name"] for supplier in supplier_metadata):
        st.error("Every uploaded PDF needs a supplier name.")
    elif len({supplier["supplier_name"].casefold() for supplier in supplier_metadata}) != len(supplier_metadata):
        st.error("Supplier names must be unique within a run.")
    else:
        endpoint_parts = urlsplit(base_url)
        safe_endpoint = f"{endpoint_parts.scheme}://{endpoint_parts.hostname or 'unknown-host'}{endpoint_parts.path}"
        app_logger.info(
            "UI evaluation submitted: supplier_count=%d model=%s endpoint=%s",
            len(supplier_metadata), model, safe_endpoint,
        )
        try:
            client = OpenAICompatibleClient(api_key=api_key, model=model, base_url=base_url)
            with st.spinner("The Orchestrator is extracting and evaluating each proposal, then calculating the leaderboard…"):
                result = run_evaluation(DATABASE_PATH, supplier_metadata, client)
            st.session_state["last_run_result"] = result
            st.success(f"Evaluation completed. Run ID: {result['rfp_run_id']}")
            st.session_state["_clear_evaluation_inputs"] = True
            st.rerun()
        except Exception as exc:
            evaluation_failed = True
            safe_error = str(exc).replace(api_key, "[REDACTED API KEY]")[:600]
            app_logger.error("UI evaluation failed: error_type=%s message=%s", type(exc).__name__, safe_error)
            st.error(f"Evaluation failed: {exc}")
            st.info("Open the diagnostic log below for the request ID and pipeline steps. API keys and proposal text are excluded.")
    # Drop the local reference as soon as processing or validation finishes.
    api_key = ""

result = st.session_state.get("last_run_result")

with st.expander("Diagnostic logs", expanded=evaluation_failed):
    st.caption(f"Log file: {LOG_PATH}")
    try:
        log_lines = LOG_PATH.read_text(encoding="utf-8").splitlines()[-200:]
        if log_lines:
            st.code("\n".join(log_lines), language="text")
        else:
            st.caption("No log entries yet. Run an evaluation to populate this log.")
    except OSError as log_exc:
        st.warning(f"Could not read diagnostic log: {log_exc}")

if result:
    st.header("Leaderboard")
    st.caption(f"RFP_RUN_ID: `{result['rfp_run_id']}`")
    leaderboard = [
        {
            "Rank": supplier["final_rank"],
            "Supplier": supplier["supplier_name"],
            "Absolute score": round(supplier["absolute_score"], 2),
            "PPI": round(supplier["ppi"], 2),
            "Submission date": supplier["submission_date"],
            "Experience rating": supplier["experience_rating"],
        }
        for supplier in result["suppliers"]
    ]
    st.dataframe(leaderboard, hide_index=True, use_container_width=True)

    supplier_names = [supplier["supplier_name"] for supplier in result["suppliers"]]
    selected_name = st.selectbox("Detailed scorecard", supplier_names)
    selected_supplier = next(s for s in result["suppliers"] if s["supplier_name"] == selected_name)
    st.subheader(f"{selected_supplier['supplier_name']} — rank {selected_supplier['final_rank']}")
    if selected_supplier.get("overall_summary"):
        st.write(selected_supplier["overall_summary"])
    if selected_supplier.get("risks"):
        st.markdown("**Risks identified**")
        for risk in selected_supplier["risks"]:
            st.markdown(f"- {risk}")

    st.dataframe(
        [
            {
                "Criterion": criterion["criterion_name"],
                "Score": f"{criterion['score']:g} / {criterion['max_score']:g}",
                "Weight": f"{criterion['weight']:g}%",
                "Benchmark": f"{criterion['benchmark_score']:g}",
                "Gap": f"{criterion['gap']:+g}",
                "Relative performance": f"{criterion['relative_performance']:.1f}%",
                "Evidence": criterion["evidence"],
                "Justification": criterion["justification"],
            }
            for criterion in selected_supplier["criteria"]
        ],
        hide_index=True,
        use_container_width=True,
    )
    if any(criterion["zero_benchmark_parity"] for criterion in selected_supplier["criteria"]):
        st.caption("For any criterion where all suppliers scored zero, relative performance is shown as 100% to indicate peer parity.")

    st.markdown("**Ranking tie-break order**")
    st.write("Higher PPI → earlier submission date → higher historical experience rating → supplier name ascending.")
    if result.get("warnings"):
        with st.expander(f"Run warnings ({len(result['warnings'])})"):
            for warning in result["warnings"]:
                st.markdown(f"- {warning}")

    st.download_button(
        "Download complete run as JSON",
        data=json.dumps(result, ensure_ascii=False, indent=2),
        file_name=f"rfp-run-{result['rfp_run_id']}.json",
        mime="application/json",
        use_container_width=True,
    )
