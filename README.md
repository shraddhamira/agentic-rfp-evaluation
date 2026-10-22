# Agentic RFP Evaluation

A local-first Streamlit application for evidence-backed supplier proposal evaluation. The Orchestrator Agent coordinates specialist agents and tools; deterministic Python code validates scores, calculates peer metrics, and ranks suppliers.

## Project status

Step 8 foundation. The Streamlit workflow displays criteria, accepts supplier PDFs and metadata, requests LLM connection details, runs the Orchestrator, and presents rankings, scorecards, warnings, and JSON export. Four fictional two-page proposals are included in `sample_proposals/`. An offline Orchestrator demo and sample JSON export are included; the live provider connection and deployment still need a user API key and provider selection.

## Requirements

- Python 3.11 or newer
- Streamlit
- SQLite (included with Python)
- PDF text extraction with `pypdf`
- Schema validation with Pydantic
- A JSON-capable LLM provider with an OpenAI-compatible endpoint (or a future adapter for another API)
- An OpenAI-compatible chat-completions endpoint with JSON object mode for the current adapter

## Setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
python scripts/init_db.py
streamlit run app.py
```

## Architecture

1. `orchestrator.py` coordinates each run and calls agents or tools as needed.
2. `document_tool.py` extracts text from uploaded proposal PDFs.
3. `evaluation_agent.py` asks an OpenAI-compatible JSON endpoint for one evidence-backed score per active criterion.
4. `validation_tool.py` validates and normalizes the response, recording warnings.
5. `ranking_tool.py` calculates scores and ranks in deterministic Python code.
6. `database.py` loads criteria, snapshots each run's criteria, and persists complete results in SQLite.
7. `app.py` will provide the Streamlit user interface and pass a UI-entered API key to a run-scoped client.

## Scoring decisions

- Active criteria weights must total 100%.
- Absolute score is the weighted sum of `criterion score / criterion maximum`, on a 0–100 scale.
- Criterion benchmark is the best normalized score across suppliers in the run; gap is supplier score minus benchmark.
- Relative performance is score divided by benchmark times 100. If all suppliers score zero for a criterion, relative performance is 100% for each to express parity; the scorecard will label this case.
- PPI is the weighted average of criterion relative-performance percentages.
- Ranking order: higher PPI, earlier submission date, higher experience rating, then supplier name ascending.
- Criterion gaps are expressed in criterion score points; absolute scores use the normalized 0–100 scale.

## API key handling

The Streamlit form requests an OpenRouter API key in a password field. It is passed to the run-scoped client and excluded from SQLite, prompts, and results. Inputs remain in the active Streamlit browser session after a failed evaluation so the user can correct settings and retry; after a successful evaluation, the form inputs (including the key) are cleared. The model dropdown contains five options, with `openrouter/free` selected by default; OpenRouter routes it to an available free model. Four OpenAI models are also available through OpenRouter. The default API base URL is `https://openrouter.ai/api/v1`. Rotating diagnostics are written to `data/agentic_rfp.log` and displayed in the app. The default file is limited to 1 MB, with up to three 1 MB rotated backups; set `AGENTIC_RFP_LOG_PATH` to override its location. Streamlit Community Cloud has ephemeral storage, so logs there are temporary; use the Cloud app logs for operational diagnostics. The file includes pipeline stages and sanitized provider errors but never API keys or proposal text. The adapter accepts an OpenAI-compatible base URL and model. No API key is needed to set up or launch the app.

## Data and privacy

The `data/` directory is reserved for the local SQLite database. The generated fictional proposals are stored in `sample_proposals/`. Do not place real confidential proposals in the sample folder.

## Synthetic sample proposals

The sample PDFs use a fictional Northbridge Municipal Services procurement request, but use different proposal layouts and section orders: Apex Systems has a formal RFP-response structure, BrightPath Tech uses a price-led quotation, NexaWorks foregrounds its delivery plan, and Orbit Digital leads with supplier qualifications and references. Their substantive profiles also differ: Apex emphasizes technical design and security at a higher price; BrightPath offers the lowest price and fastest schedule but leaves assurance and experience details open; NexaWorks is balanced with a detailed delivery and support plan; Orbit emphasizes references and experience while leaving integration details less defined. All organizations, people, references, and figures in the PDFs are invented.

Regenerate the PDFs after installing the project dependencies:

```powershell
python scripts/generate_synthetic_proposals.py
```

## Offline demonstration

Run the complete PDF extraction, Orchestrator, validation, deterministic scoring, ranking, and SQLite persistence flow without an API key:

```powershell
$env:PYTHONPATH = "src"
python scripts/demo_run.py
```

This demonstration uses a deterministic mock evaluator and does not call an LLM provider. BrightPath's mock response intentionally includes a malformed score, a score above the allowed maximum, and a missing criterion. The validator defaults or clips those values and records warnings. The resulting complete run is exported to `sample_run.json`; its `demo_mode` field identifies the mock evaluator. This confirms the local workflow and validation handling, not a live provider connection.
