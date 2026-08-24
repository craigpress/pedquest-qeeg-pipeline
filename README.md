---
tags:
  - domain/eeg-monitoring
  - project/qeeg-pipeline
  - domain/research-methods
  - type/reference
---

# PedQuEST qEEG Analysis Pipeline

Quantitative EEG feature extraction and visualization for continuous EEG monitoring research.
Built for the [PedQuEST](https://www.pedquest.org) and POCCA studies at the University of Michigan.

Processes Persyst EEG Trends CSV exports into time-binned quantitative features with an
interactive dashboard, comprehensive data exports (Parquet + CSV), and cohort-level dataset
generation ready for R, Python, and Stata.

---

## Documentation

**All documentation lives in [`docs/`](docs/). Start at [`docs/INDEX.md`](docs/INDEX.md)** —
it is the canonical entry point and routes every topic to a single source-of-truth file.

| If you want to… | Read |
|---|---|
| Understand how a recording becomes analysis-ready, and what every column means | [`docs/INGESTION_AND_TIMEBASE.md`](docs/INGESTION_AND_TIMEBASE.md) |
| Understand binning, statistics, effective-N, and the output shapes | [`docs/EXPORT_AND_BINNING.md`](docs/EXPORT_AND_BINNING.md) |
| Look up one specific column by name | [`docs/COLUMN_MAP_V10_RESEARCH_TRENDS.md`](docs/COLUMN_MAP_V10_RESEARCH_TRENDS.md) — renders on GitHub; `.csv`/`.json` hold all 34 fields |
| Onboard as a fresh contributor | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Onboard as a PI / statistician | [`docs/ONBOARDING_PI.md`](docs/ONBOARDING_PI.md) |
| Understand Persyst panels, instruments, engines | [`docs/PERSYST_V10_REFERENCE.md`](docs/PERSYST_V10_REFERENCE.md) |
| See the dashboard panel layout + columns each row plots | [`docs/PANEL_REFERENCE.md`](docs/PANEL_REFERENCE.md) |
| Look up an exported column's meaning, units, derivation | [`docs/DATA_DICTIONARY_v4.md`](docs/DATA_DICTIONARY_v4.md) |
| Understand engine cadence / effective-N | [`docs/TREND_ENGINE_REFERENCE.md`](docs/TREND_ENGINE_REFERENCE.md) |
| Read the statistical methods + audit rules | [`docs/STATISTICAL_METHODS_AND_AUDIT.md`](docs/STATISTICAL_METHODS_AND_AUDIT.md) |
| Run a cohort-lock / freeze for analysis | [`docs/RUNBOOK_FREEZE_ANALYSIS.md`](docs/RUNBOOK_FREEZE_ANALYSIS.md) |
| Audit a publication pre-submission | [`docs/STATISTICAL_REVIEWER_CHECKLIST.md`](docs/STATISTICAL_REVIEWER_CHECKLIST.md) |

Per-topic anti-drift rule lives in [`docs/INDEX.md`](docs/INDEX.md) — when a fact changes,
update only the canonical doc; everything else links back here.

---

## The shipped template

This release reads Persyst trend CSVs exported from **one** MMX template, and only that one:

```
Ref Files/PedQuEST_Pennsieve_V10_research.mmx
sha256  213ebcd7dece6b61d86b33b78cf0d462d35736bd4456193eaf54a095384a397a
        765,388 bytes - 22 panels, 10 engines, 370 instruments
```

Column identity comes from an instrument's **position in the export panel**, which is a
property of that template — so an export from a different template resolves to different
columns under the same names. Every patient's MMX fingerprint is recorded in provenance,
and a cohort must resolve to exactly one. Earlier templates are kept under `_archive/`
for provenance only; they are not readable by this release.

Verify a copy before trusting a run:

```bash
python -c "import hashlib,pathlib;print(hashlib.sha256(pathlib.Path('Ref Files/PedQuEST_Pennsieve_V10_research.mmx').read_bytes()).hexdigest())"
```

Two families are deliberately **not** exported: the 18 Artifact Detector columns (Persyst
describes them as internal classifiers, not measurements) and any electrode identity for the
Electrode Signal Quality channels (the export cannot support it, so ESQ is numbered
positionally as `esq_ch01…esq_chNN`). See [`docs/ARTIFACT_EXCLUSION.md`](docs/ARTIFACT_EXCLUSION.md).

---

## Requirements

- **Python 3.11+** (3.13 recommended)
- **Node.js 20+** with npm (only needed once, to build the frontend)
- Windows 10/11 (tested), macOS, or Linux

---

## Install

```bash
git clone https://github.com/craigpress/qeeg-analysis-pipeline.git
cd qeeg-analysis-pipeline
pip install -e .
cd frontend && npm install && npm run build && cd ..
```

`pip install -e .` is the only supported install path. Subdirectory `requirements.txt` files
are legacy reference only.

---

## Run

```bash
python start.py                    # default port 8000
python start.py --port 9000        # custom port
python start.py --dev              # dev mode (Vite hot-reload)
```

The launcher verifies dependencies, frees the port, starts FastAPI, and opens your browser.

**Development mode caveat:** delete `frontend/dist/` first. If `dist/` exists, the FastAPI
static mount shadows the Vite proxy and you see the last production build instead of live
changes. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full dev workflow.

---

## Testing

```bash
python -m pytest --ignore=tests/test_stress_gui.py -q
```

Generate synthetic stress-test data (5 patients × 48 h):

```bash
python tests/generate_stress_data.py
```

---

## Project layout

```
qeeg/      # core processing library (ingestion, analysis, features, storage, alignment, quality, validation)
api/       # FastAPI backend (routes, services, models)
frontend/  # React + Vite + Zustand + Recharts
tests/     # pytest suite + stress data generator
docs/      # all documentation — start at docs/INDEX.md
```

For full module-by-module map see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §3.
