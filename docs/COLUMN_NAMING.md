---
tags:
  - domain/eeg-monitoring
  - project/qeeg-pipeline
  - domain/research-methods
  - type/reference
---

# Column naming

How a Persyst export column gets its identity and its name. The shipped
template `Ref Files/PedQuEST_Pennsieve_V10_research.mmx` is the only source of
truth; no earlier template is supported.

Every claim here is checked against the four real subject-1 exports and re-verified
on each test run by `tests/test_column_resolution.py` (with the research share)
and `tests/test_column_resolution_synthetic.py` (without it).

---

## 1. Identity comes from panel position

A Persyst CSV header carries two rows: a display label and an I-code
(`I{group}_{sub}`). Neither is a stable key on its own.

**The I-group is the instrument's 1-based position in the export panel.** Persyst
serialises the panel in display order and appends two pseudo-columns:

```
len(panel.instruments) + 2  ==  max(i_group)          the +2 is Comment and Time
```

Verified with zero violations on all four exports — `Research-Trends` 238 + 2 →
`I240`, `Research` 370 + 2 → `I372`. `resolve_export_panel()` uses it to identify
which panel an export came from, with no configuration.

**Independent confirmation:** at every one of the 238 positions, the CSV trend
text begins with that instrument's own MMX label (`GraphTitle`, or `Name` when
empty). That check never consults the ordinal rule, so it is evidence *for* it,
not a restatement. See `_project/audits/COLUMN_ASSIGNMENT_REVIEW.md` §3.4.

**When the panel cannot be identified**, resolution degrades to name lookup and
then regex. Several panels share an instrument count (four have 11, three have
13), so this is reachable. Every column records which method applied, and exports
publish the mix — see §4.

### Why not match on the trend name

MMX instrument names are internal expressions; the CSV carries display labels.

```
MMX   "= 0 <0> [SleepStages]"
CSV   "aEEG, All 10-20"
```

Exact-matching them resolves **1 of 294 columns**. Worse, Persyst ships distinct
instruments under *identical* labels — six sleep stages, seizure probability vs
detections, left vs right vs bilateral spike detectors — so no name-based method
can separate them. Position is the only discriminator.

### Two rules that follow

- **The MMX is authoritative for identity and channels; the display label is
  authoritative for meaning.** For derived Boolean detectors the MMX name is the
  underlying *formula*, so its inferred family describes the substrate rather
  than the measurement. Taking family from the MMX regressed 72 columns
  (`pd_lad` → `rhythmicity_left_anterior_1_00hz`). Conversely, anything the label
  does not carry — an averaging window, a sub-column's role — must come from the
  MMX: Persyst does not update a display label when the underlying window changes.
- **Absolute I-numbers are never used** — not in identifiers, not in lookup
  tables. They shift whenever the panel is edited. Ordinal *rank within one
  export* is used, because that is how Persyst serialises.

## 2. Name construction

`common_name` is the exported column name: a valid Python/R identifier. Both the
single-file and multi-segment paths rename their dataframe columns to it, so one
recording gives one vocabulary however it is processed.

```
{family}_{anatomy}_{band or frequency}_{sub-column}
```

| Part | Source |
|---|---|
| family | the display label, via `classify_family()` |
| anatomy | MMX `Channels`, falling back to the label (`left_anterior`, `all`, electrode chain) |
| band / frequency | the label's band ratio, or the schema's bin-centre formula |
| sub-column | resolved instrument where the label is ambiguous |

**Ratios classify by denominator, not by wording** — the numerator cannot
distinguish them. The keyword pass runs first; only power-ish families are then
re-routed through `classify_ratio`, so a band ratio appearing in an aEEG or
suppression label cannot pull that trend into `relative_power`.

```
band / 1-30   relative_power     fraction (0–1)         rel_alpha_all
6-14 / 1-20   alpha_variability  ratio, unbounded       rav_all
8-13 / 1-4    adr                                       adr_left_hemisphere
4-8  / 1-4    adr (tdr)
```

RAV is Relative Alpha **Variability** — Persyst pins it to `6-14/1-20`, and the
panels named "Relative Alpha Variability" contain only that ratio. It is a
dispersion statistic, observed to 116, so it is *not* a proportion. The four
relative-power bands are, and sum to 1.000000 within a region.

**Where the label cannot disambiguate**, the resolved instrument supplies the
missing token:

| Columns | Shared label | Discriminator |
|---|---|---|
| 6 sleep stages | `SleepStages` | expression `= N <0> [SleepStages]` |
| rhythmic delta ×3 | `blue=left, red=right, green=gen` | `Left AND NOT[Right]` → left; plain `Left AND Right` → generalized |
| spike detectors | `blue=left, red=right` | electrode set; `AND NOT[…]` → one-sided, plain `AND` → bilateral, `SpikeGen` → generalized |
| seizure prob/detect | one label | MMX suffix `Probability` / `Detections` |
| `Time Max/Avg/Min <0,N>` | same as its source | window token, so a derived channel never takes its source's name |

Both laterality rules strip the negated clause and score what remains. Splitting
on a bare `" AND "` instead makes the both-sides case unreachable, which is how a
bilateral detector once came to be named `left`.

## 3. Uniqueness

Two columns sharing a name is a silent overwrite in any dataframe. After
resolution, `ensure_unique_common_names()` guarantees uniqueness and logs every
rename.

Persyst does ship genuinely identical instruments — the `Research` panel carries
two `Asymmetry, Relative Index (REASI) 4-8 Asym Hemi` entries with the same name
and definition, separable only by position. All naturally-occurring names are
reserved first, then later duplicates take a `__dup2`, `__dup3` suffix, which the
naming scheme cannot itself emit. Reserving first matters: a synthesised `foo_2`
must not displace an instrument Persyst already named `foo_2`.

## 4. Versioning and provenance

`COLUMN_SCHEMA_VERSION` tracks the column vocabulary, separately from
`__version__`: not *which code produced this dataset* but *which column names it
speaks*. It is stamped into export metadata alongside the resolution mix:

```json
"column_schema_version": 7,
"column_resolution": {"by_method": {"ordinal": 291, "tail": 2},
                      "fully_ordinal": true, "non_ordinal_columns": 0}
```

`fully_ordinal: false` means the panel could not be identified and the columns
were classified from text — the version stamp alone cannot tell you that.

**Any `common_name` change bumps `COLUMN_SCHEMA_VERSION` and regenerates the
fixture.** A rename is indistinguishable from a broken join in an analysis
script — both look like a column that isn't there — so the stamp is what lets a
downstream script tell the two apart. No dataset exists under an earlier
vocabulary, so there is nothing to migrate from.

`ColumnEntry.source_code` keeps the Persyst I-code after `code` becomes the slug,
so the data dictionary's `original_code` still reports it.

## 5. Guards

| Guard | Catches |
|---|---|
| `scripts/refresh_ref_mmx.py --check` | committed MMX drifting from the live install (exit 1 stale, exit 2 unverifiable) |
| `tests/test_column_resolution.py` | any `common_name`, family, sub-column or `resolution` change, asserted per column against the frozen fixture |
| `tests/test_column_resolution_synthetic.py` | the same resolution rules, with no research share |
| `validate_subcol_counts()` (in the pipeline) | a family's sub-column count moving |
| `ensure_unique_common_names()` | duplicate identifiers |

## 6. Known unresolved

**Rhythmicity FreqPow positions 2 and 4.** The 16 sub-columns are 4 bands × 4
values. Positions 1 and 3 are confirmed against the §3.25 SumValues scalars
(peak frequency, integrated power); 2 and 4 are documented as *not confirmed* in
the format reference, so they carry positional labels `_v2` / `_v4` rather than
invented names. Band edges follow Persyst's help page
(`1-4 / 4-9 / 9-16 / 16-25 Hz`), which the data supports — position-1 maxima are
3.96 / 8.59 / 13.89 / 22.90 Hz, outside the conventional theta and alpha ranges.
Band names are only applied at the documented 16-sub-column layout. **Query with
Persyst outstanding.**

These columns exist only in the full `Research` panel, so their absence from a
limited `Research-Trends` export is expected, not a fault.

**`rda_generalized`.** Vendor-faithful (Persyst's legend says "gen"), but it is a
conjunction of two independent regional detectors: it establishes that both
hemispheres are active, not the synchrony and symmetry ACNS 2021 requires for
"G". The caveat ships in the data dictionary via `_COMMON_NAME_NOTES`. **Query
with Persyst outstanding.**
