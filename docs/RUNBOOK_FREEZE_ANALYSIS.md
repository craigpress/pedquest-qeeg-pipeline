---
tags:
  - domain/eeg-monitoring
  - project/qeeg-pipeline
  - domain/research-methods
  - type/reference
---

# Runbook — Freeze a Cohort for Analysis

Goal: produce an immutable, reproducible cohort snapshot that binds a
specific code commit, pipeline config, MMX file, clinical metadata,
corrections, and raw EEG CSVs to a fixed analysis dataset. Any future
publication must be able to regenerate exactly the numbers in the paper
from this snapshot.

## Freeze trigger — MMX finalization

A cohort lock is triggered by **finalization of the study MMX file**.
Until the MMX is final, no cohort export is publication-bound. The MMX
defines the panels, instruments, trend calculations, channels, frequency
bands, and engine cadences that determine every downstream feature; a
mid-cohort MMX change invalidates the entire dataset.

The lock procedure below assumes the study MMX has been signed off and
its SHA-256 will not change for the duration of the analysis.

| Pre-lock action | Owner | Verification |
|---|---|---|
| Study MMX finalized and signed off | PI | MMX file has a stable SHA-256 captured in every patient's `audit_bundle.json` |
| All study patients re-imported with the final MMX | Pipeline operator | Each `meta.json` references the finalized MMX path |
| Clinical metadata table version-locked | Study coordinator | SHA-256 in audit bundle |
| EEG corrections table version-locked | Study coordinator | SHA-256 in audit bundle |

If any of these change after the lock, **do not patch the lock** — start
a new lock with a new tag.

## Pre-freeze checks

1. **Tests pass.**
   ```powershell
   python -m pytest --ignore=tests/test_stress_gui.py -q
   ```
   Every failing test is a freeze-blocker.
2. **Worktree is clean.**
   ```powershell
   git status --porcelain
   ```
   No output; uncommitted changes invalidate provenance.
3. **Cache schema aligned with code.**
   ```powershell
   python -c "from qeeg.storage.result_cache import CACHE_SCHEMA_VERSION; print(CACHE_SCHEMA_VERSION)"
   ```
   Value must match the `v{N}` marker inside the target patient cache's
   `cache_key` in `meta.json`.
4. **Sub-col contract validator passes for every cohort patient.**
   ```powershell
   # Runs qeeg.ingestion.subcol_validator against the parsed CSV header of
   # every cohort patient and aggregates the reports. Any error-severity
   # mismatch is a freeze-blocker; warn-severity entries (e.g. Electrode
   # Signal Quality channel count) are acceptable but must be recorded.
   python -m pytest tests/test_subcol_validator.py -q
   ```
   Required because sub-col semantics are now keyed by trend family
   (MMX-version-independent) rather than I-group, and the validator is the
   single line of defense against silent slug drift.
5. **No legacy aEEG slugs remain in any cohort patient's cache schema.**
   The 2026-05-21 aEEG rename replaced `upper_margin / lower_margin /
   bandwidth / percent_bs / amplitude` with `max / min / p50 / p75 / p25`.
   Patient caches written before that commit must be reprocessed.
   ```powershell
   # Returns nothing if all caches are clean; prints offending patient cache
   # dirs if legacy aEEG slugs are still present.
   python -c "from pathlib import Path; import json, sys
   bad = []
   for meta in Path('.qeeg_cache').rglob('schema.json'):
       cols = set(json.loads(meta.read_text()).get('columns', []))
       legacy = {'aeeg_left_upper_margin', 'aeeg_left_lower_margin', 'aeeg_left_bandwidth', 'aeeg_left_percent_bs', 'aeeg_left_amplitude', 'aeeg_right_upper_margin', 'aeeg_right_lower_margin', 'aeeg_right_bandwidth', 'aeeg_right_percent_bs', 'aeeg_right_amplitude'}
       if cols & legacy: bad.append(str(meta.parent))
   print('\n'.join(bad) if bad else 'OK')"
   ```
6. **Cohort MMX hash is single-valued.**
   The I-group → family mapping is template-specific, so each patient's
   MMX hash must be in provenance and the cohort must resolve to exactly
   one distinct hash. Collect them and assert `len(set(hashes)) == 1`.
   More than one means patients were exported from different templates —
   investigate and re-export, rather than modelling the difference as
   missingness.
7. **Data dictionary snapshot version is current.**
   The cohort lock must reference the latest committed
   `docs/DATA_DICTIONARY_v{N}.md`. Column-name breaks (e.g. the 2026-05
   aEEG rename) require a major-version bump of the dictionary; the new
   snapshot's SHA-256 must be in the audit bundle.
8. **Frontend type-clean.**
   ```powershell
   cd frontend ; npm run lint
   ```

## Freeze procedure

1. **Tag the code commit.**
   ```bash
   git tag -a cohort-lock/<study>-<YYYY-MM-DD> -m "Cohort lock for <study> analysis"
   git push origin cohort-lock/<study>-<YYYY-MM-DD>
   ```

2. **Reprocess every patient in the cohort from clean cache.**
   ```bash
   # delete only the cohort patients' cache dirs; leave others intact
   rm -rf .qeeg_cache/*_<patient_id>   # repeat per patient
   # then reprocess via the API
   curl -X POST http://localhost:8000/api/pipeline/reprocess/<patient_id> \
        -H "Content-Type: application/json" -d '{}'
   ```

3. **Generate research packages.**
   Per-patient:
   ```bash
   curl -X POST http://localhost:8000/api/export/<patient_id>/package -o <patient_id>.zip
   ```
   Cohort:
   ```bash
   curl -X POST http://localhost:8000/api/export/cohort -d '{"patient_ids":[…]}' -o cohort.zip
   ```

4. **Generate audit bundles.**
   For each patient, build and commit the `audit_bundle.json`:
   ```python
   from pathlib import Path
   from qeeg.storage.audit_bundle import build_audit_bundle, write_audit_bundle
   bundle = build_audit_bundle(
       patient_id="P-001",
       config=cached_config,
       raw_inputs=[Path("raw/P-001.csv")],
       auxiliary_inputs=[Path("metadata.csv"), Path("corrections.csv")],
       generated_exports=[Path("P-001_epochs.parquet"), Path("P-001_bin_summary.parquet")],
       stage_row_counts={"parsed": ..., "usable": ..., "binned": ...},
       mmx_path=Path("Ref Files/PedQuEST.mmx"),
       cache_dir=Path(".qeeg_cache/<hash>_P-001"),
   )
   write_audit_bundle(bundle, Path("cohort_lock/P-001.audit_bundle.json"))
   ```

5. **Recompute audit against each patient.**
   ```bash
   python scripts/audit_recompute.py --cache-dir .qeeg_cache/<hash>_<pid>
   ```
   Zero `not_checked` items in publication-bound fields; zero mismatches.

6. **Immutable copy.**
   Copy the following to a read-only, backed-up location (e.g. a study
   archive drive):
   - Tagged git commit archive (`git archive --format=zip
     cohort-lock/… -o code.zip`)
   - Every raw CSV, MMX, clinical metadata, corrections file
   - Every generated export ZIP
   - Every `audit_bundle.json`
   - The SAP (completed from
     [`STATISTICAL_ANALYSIS_PLAN_TEMPLATE.md`](STATISTICAL_ANALYSIS_PLAN_TEMPLATE.md))

7. **Record lock.**
   Append to `docs/cohort_locks.md` (create if absent) a row with:
   `date | tag | study | n_patients | pipeline_version | cache_schema | frozen_path`.

## Unfreezing

Do not. If the pipeline or inputs change, create a new lock with a new
tag; the old lock remains valid for its paper.

## If the audit fails

- `not_checked` items → investigate whether the audit script can be
  extended, or whether the field depends on a missing epoch column
  (e.g. `_is_independent_<engine>` for non-FFT cadence-adjusted N).
- `mismatch` items → treat as a ship-blocker. Do not freeze until root
  cause is diagnosed.
