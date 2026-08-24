---
tags:
  - domain/eeg-monitoring
  - project/qeeg-pipeline
  - domain/research-methods
  - type/reference
---

# PedQuEST qEEG Pipeline — Documentation Index

This is the canonical entry point. Every other doc in `docs/` is linked from
here with one designated topic owner — if a fact appears in multiple files,
the **canonical** column wins and the others must defer.

> **Anti-drift rule.** When a topic changes, update only the canonical doc.
> All other docs must link back here, not copy the content. If you catch a
> duplicate, copy → link.

Last refreshed: **2026-05-27**.

---

## 1. Start here

**The two flagship docs** cover a recording end to end, and between them answer most
questions without a detour:

| | Document |
|---|---|
| A recording becomes analysis-ready — T0/ROSC, recording start, stitching, date corrections, and what every exported column means | [`INGESTION_AND_TIMEBASE.md`](INGESTION_AND_TIMEBASE.md) |
| Analysis-ready data becomes a dataset — bins, statistics, effective-N, coverage, output shapes | [`EXPORT_AND_BINNING.md`](EXPORT_AND_BINNING.md) |

| Audience | Document |
|---|---|
| Fresh model / new contributor | [`ARCHITECTURE.md`](ARCHITECTURE.md) — single-document framework + codebase onboarding |
| Principal investigator / statistician | [`ONBOARDING_PI.md`](ONBOARDING_PI.md) — one-page orientation |
| Operator running an analysis | [`RUNBOOK_FREEZE_ANALYSIS.md`](RUNBOOK_FREEZE_ANALYSIS.md) — cohort-lock procedure |
| Reviewer auditing a publication | [`STATISTICAL_REVIEWER_CHECKLIST.md`](STATISTICAL_REVIEWER_CHECKLIST.md) — pre-submission pass/fail |

---

## 2. Canonical reference (single-source-of-truth per topic)

### Persyst / MMX / CSV interpretation

| Topic | Canonical | Cross-references |
|---|---|---|
| **Sub-column meanings** (aEEG percentiles, FFT bins, etc.) | [`Ref Files/PersystTrendCSV_Format_Reference.md`](../Ref%20Files/PersystTrendCSV_Format_Reference.md) §3 | `PERSYST_V10_REFERENCE.md` §7 summarizes; `qeeg/ingestion/subcol_schema.py` is the Python mirror. Persyst publishes no CSV layout spec, so this reference is reverse-engineered from exports and the MMX — not a vendor document |
| **MMX catalog** (panels × instruments × engines) | [`PERSYST_V10_REFERENCE.md`](PERSYST_V10_REFERENCE.md) | [`persyst_v10_catalog.json`](persyst_v10_catalog.json) (machine-readable), [`persyst_v10_panel_index.md`](persyst_v10_panel_index.md) (per-panel), [`persyst_families.generated.md`](persyst_families.generated.md) (family facts); all regen via `scripts/sync_persyst_docs.py`. |
| **Engine cadence / effective-N** | [`TREND_ENGINE_REFERENCE.md`](TREND_ENGINE_REFERENCE.md) | n/a |
| **Workbench panel layout** (UI panels and the columns each row plots) | [`PANEL_REFERENCE.md`](PANEL_REFERENCE.md) | `frontend/src/panels/instruments.ts` is the executing source of truth for the UI |

### Pipeline / architecture

| Topic | Canonical | Cross-references |
|---|---|---|
| **Framework + codebase map** | [`ARCHITECTURE.md`](ARCHITECTURE.md) | Section 3 lists every module |
| **Data dictionary** (per-column meaning in the binned export) | [`DATA_DICTIONARY_v4.md`](DATA_DICTIONARY_v4.md) | `docs/_archive/DATA_DICTIONARY_v3.md` superseded (kept for pre-2026-05-21 cohort locks); `docs/_archive/DATA_DICTIONARY_STATISTICAL_REVIEW.md` annotated v3 statistical implications |
| **Statistical methods + audit rules** | [`STATISTICAL_METHODS_AND_AUDIT.md`](STATISTICAL_METHODS_AND_AUDIT.md) | `STATISTICAL_ANALYSIS_PLAN_TEMPLATE.md` is the per-study template |
| **Dashboard panel layout** (the implemented UI — supersedes earlier design-overhaul draft) | [`PANEL_REFERENCE.md`](PANEL_REFERENCE.md) | Frozen 2026-04-11 design draft archived at `docs/_archive/display_overhaul_design.md` |
| **Data flow diagrams** | [`DATA_FLOW_FIGURES.md`](DATA_FLOW_FIGURES.md) | n/a |

### Operations

| Topic | Canonical | Cross-references |
|---|---|---|
| **Cohort lock / freeze procedure** | [`RUNBOOK_FREEZE_ANALYSIS.md`](RUNBOOK_FREEZE_ANALYSIS.md) | n/a |
| **Pre-submission reviewer checklist** | [`STATISTICAL_REVIEWER_CHECKLIST.md`](STATISTICAL_REVIEWER_CHECKLIST.md) | n/a |

### Column naming

| Topic | Canonical | Cross-references |
|---|---|---|
| **How a column gets its identity and name** | [`COLUMN_NAMING.md`](COLUMN_NAMING.md) — **start here** | identity comes from panel position in the shipped MMX |
| **Which vocabulary an export speaks** | `column_schema_version` in every export's provenance | `qeeg/__version__.py` records what each version changed |

### Per-column map (generated from the shipped MMX)

| Topic | Canonical | Cross-references |
|---|---|---|
| **Every column of a Research-Trends export** | [`COLUMN_MAP_V10_RESEARCH_TRENDS.md`](COLUMN_MAP_V10_RESEARCH_TRENDS.md) — **start here, renders on GitHub** · [`.csv`](COLUMN_MAP_V10_RESEARCH_TRENDS.csv) · [`.json`](COLUMN_MAP_V10_RESEARCH_TRENDS.json) · [`.html`](COLUMN_MAP_V10_RESEARCH_TRENDS.html) (local only) | 301 columns. One row per exported column: I-code, CSV header, MMX instrument, `variable_name`, family, units, power scale, band, region, engine cadence, resolution method, evidence tier. |
| **Every column of the full Research panel** | [`COLUMN_MAP_V10_FULL_RESEARCH_PANEL.md`](COLUMN_MAP_V10_FULL_RESEARCH_PANEL.md) — **start here** · [`.csv`](COLUMN_MAP_V10_FULL_RESEARCH_PANEL.csv) · [`.json`](COLUMN_MAP_V10_FULL_RESEARCH_PANEL.json) · [`.html`](COLUMN_MAP_V10_FULL_RESEARCH_PANEL.html) (local only) | 4,106 columns — the spectrogram families included. Same schema as above. |

The `.md` is the one to open in a browser: GitHub serves `.html` from a repo as
source rather than rendering it, and stops rendering `.csv` once the file gets
large — the full panel is 1.4 MB. Both are regenerated by `scripts/gen_column_map_v10.py`, which resolves every
column through the production path (`build_column_schema_with_mmx`) against the
shipped template — so the map cannot drift from what ingestion actually does.
Each row carries an **evidence tier** (§2.1 of the release spec): `P-DOC`
vendor-documented, `P-COMM` direct Persyst communication, `MMX` read from the
template, `EMP` empirical/inferred. Treat `EMP` rows as provisional.

> Dated audit records that established the panel-ordinal rule live under
> `docs/_project/audits/`. They cite pre-2026-08 identifiers and are kept as
> provenance, not as a current column list.

### Schema as code (source of truth for sub-col semantics)

| Topic | Canonical (Python) | Doc mirror |
|---|---|---|
| Sub-col counts + slugs + bin frequencies | [`qeeg/ingestion/subcol_schema.py`](../qeeg/ingestion/subcol_schema.py) | `PersystTrendCSV_Format_Reference.md` §3 |
| Sub-col contract validation | [`qeeg/ingestion/subcol_validator.py`](../qeeg/ingestion/subcol_validator.py) | Schema-driven |
| Family/engine cadence resolution | [`qeeg/ingestion/cadence.py`](../qeeg/ingestion/cadence.py) | `TREND_ENGINE_REFERENCE.md` |
| Trend-name → family classification | [`qeeg/ingestion/mmx_parser.py`](../qeeg/ingestion/mmx_parser.py) | `PERSYST_V10_REFERENCE.md` §3 (ClsId taxonomy) |

---

## 3. Project work files (dated, non-canonical)

These live under `docs/_project/` and capture state at a point in
time — handoffs, validation runs, planning, screenshots. They are **not**
authoritative for current state; check the canonical docs in §2 first.

> **Not shipped in the release.** The paths below exist in the development
> repository only. A dated work file describes the project as it was on its
> date, which is exactly what a release must not present as current.

| Subdirectory | Contents |
|---|---|
| `docs/_project/handoffs/` | Chronological session handoffs (newest = most authoritative within its date) |
| `docs/_project/diagnostics/` | One-off bug investigations |
| `docs/_project/validation/` | Validation runs against reference data |
| `docs/_project/plans/` | Phase/hardening plans from past and current work |
| `docs/_project/reviews/` | Code-review reports (e.g. council reviews) |
| `docs/_project/screenshots/` | UI screenshots referenced from handoffs |
| [`dev/`](dev/) | Platform-specific dev notes (kept top-level — small + evergreen) |

---

## 4. Historical / superseded (read-only)

`docs/_archive/` and the top-level `_archive/` hold superseded templates,
column crosswalks, and retired design drafts. Like §3 they are **development
repository only and not shipped** — they describe templates this pipeline can
no longer read. Anything in them is provenance: do not derive current behavior
or analysis decisions from it without re-verifying against §2.

---

## 4b. Anti-drift: how the three layers stay in sync

Persyst facts used to drift between the **GitHub docs**, the **Obsidian vault**,
and the **scripting**. They no longer can, because the derived facts are
*generated*, not hand-maintained, and a test fails on any drift.

**Source of truth (never restate these elsewhere):**

| Fact | Lives in (code) |
|---|---|
| Family classification | `qeeg/constants.py::FEATURE_FAMILIES` + `column_mapper.classify_ratio` |
| Family → unit | `qeeg/storage/export.py::_FAMILY_UNITS` |
| Family → engine / cadence | `qeeg/ingestion/cadence.py::FAMILY_ENGINE_MAP` |
| Family → export group | `qeeg/storage/export.py::_GROUP_FAMILIES` |
| Family → value range | `qeeg/validation/data_checks.py::FAMILY_VALUE_RANGES` |
| Sub-column counts / slugs / bin freqs | `qeeg/ingestion/subcol_schema.py` (mirrors `PersystTrendCSV_Format_Reference.md` §3) |
| Per-instrument catalog / panels | the committed MMX `Ref Files/PedQuEST_Pennsieve_V10_research.mmx` |

**Generated artifacts (do NOT hand-edit — run the script):**
`docs/persyst_v10_catalog.json`, `docs/persyst_v10_panel_index.md`, and
`docs/persyst_families.generated.md`. The vault's
`Projects/qEEG Analysis Pipeline/Persyst Reference/persyst_families.generated.md` is a **symlink** to the last
of these (one physical file — it cannot hold a divergent copy).

**The workflow:**
1. Change a Persyst fact → change it **only** in the code source above.
2. Run `python scripts/sync_persyst_docs.py` (regenerates all four artifacts +
   the vault block).
3. `pytest tests/test_persyst_doc_sync.py` enforces it — `--check` mode (and the
   test) fail if a generated artifact is stale or a slug collision appears. Run
   this before every push that touches `qeeg/ingestion`, `qeeg/storage/export`,
   `qeeg/validation`, or the MMX.

**Narrative docs** (`PERSYST_V10_REFERENCE.md`, `DATA_DICTIONARY_v4.md`) and the
**vault** cite `persyst_families.generated.md` for exact values rather than
restating them — so there is nothing to drift. The vault links the file via a
symlink to the repo copy; `scripts/sync_persyst_docs.py` (re)creates that symlink
when run. Windows symlink creation needs Developer Mode or an elevated shell — if
it isn't permitted, the script falls back to a generated copy and prints the
one-time `New-Item -ItemType SymbolicLink ...` command.

---

## 5. How to use this index

- **Adding new content?** Pick the canonical doc for the topic and edit it
  there. Add a cross-link from this index if it's a new topic.
- **Found drift?** Pick the canonical doc as the truth, edit the others to
  link instead of duplicate, and note the cleanup in your commit message.
- **Writing a new doc?** Before creating it, check if the topic already
  has a home in §2. If yes, extend the existing canonical doc; don't
  create a parallel file.
- **Renaming or splitting a canonical doc?** Update this index in the
  same commit.
