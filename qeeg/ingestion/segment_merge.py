"""Semantic-name merge for multi-segment Persyst exports.

Problem
-------
When a patient has multiple Persyst CSV segments exported from different MMX
panel configurations, the raw ``I{group}_{sub}`` column codes are NOT portable
between segments. The same ``I288_1`` might be a 16-bin FreqPow summary in one
segment and a 97-bin rhythmicity spectrogram bin in another. A raw
``pd.concat`` on those frames silently merges incompatible trends, producing
high-NaN stripes and cross-contaminated signals.

Fix
---
Resolve every I-code to a ``common_name`` (semantic slug from
``column_mapper.generate_common_name``) per segment and merge by that slug.
Columns with the same semantic name across segments are combined by
rank-ordered fill (highest non-NaN density wins; first-seen tiebreak).
Disjoint time windows concatenate naturally; overlapping rows (same
``ClockDateTime``) collapse to a single row per semantic column.

The emitted ``ParsedExport`` has:
- ``data``: DataFrame whose columns are ``ClockDateTime`` plus ``common_name``
  slugs. No raw ``I{group}_{sub}`` codes are exposed.
- ``code_to_description``: ``{common_name: trend_name}`` keyed by the slug.
- A pre-built ``ColumnEntry`` schema (returned alongside) so downstream
  code does not need to re-run the I-code regex builder.
"""
from __future__ import annotations

import logging
from dataclasses import replace

import numpy as np
import pandas as pd

from typing import Any, Optional

from .parser import ParsedExport
from .column_mapper import (
    ColumnEntry,
    build_column_schema,
    build_column_schema_with_mmx,
)


def _build_schema(code_to_description: dict[str, str], mmx: Optional[Any]) -> list[ColumnEntry]:
    """MMX-first when available so multi-segment patients get the same
    family/region resolution as single-segment ones."""
    if mmx is not None:
        return build_column_schema_with_mmx(code_to_description, mmx)
    return build_column_schema(code_to_description)

log = logging.getLogger(__name__)


# Slug-collision policy (updated 2026-06-10 for V8 MMX):
#
# Asymmetry-region power trends (Persyst "FFT Power, X Hz, Asym Anterior") are
# now suffixed ``_asym`` at slug-generation time (see column_mapper.
# generate_common_name), so they no longer collide with non-lateralized
# Anterior/Posterior channel power.
#
# Where a raw Persyst trend and a pipeline-computed feature would share a slug
# (e.g. native ``fft_delta_anterior`` vs the computed bilateral aggregate, or
# native ``rel_alpha_anterior`` vs the computed band-sum relative power), the
# Persyst-native value wins: compute_regional_features and compute_all_derived
# skip any output column that already exists in the frame. This is the
# "Persyst-native is the single source of truth" decision — the previous
# ``_RESERVED_DERIVED_SLUGS`` redirect that forced raw trends to ``_asym`` has
# been removed.


def _rename_segment(
    df: pd.DataFrame,
    schema: list[ColumnEntry],
) -> tuple[pd.DataFrame, dict[str, str], dict[str, ColumnEntry]]:
    """Rename a segment's I-code columns to their common_name slugs.

    Returns ``(renamed_df, slug_to_trend, slug_to_entry)``.

    Columns whose I-code has no matching schema entry or no common_name
    are dropped (they are un-interpretable downstream).

    Intra-segment slug collisions happen for a few families whose
    ``common_name`` generator does not distinguish sub_index (e.g. aEEG
    percentile sub-columns max/min/p50/p75/p25 under group I7/I8/I9,
    artifact detector per electrode under I10, electrode quality under
    I34). We disambiguate
    those by appending a position-based ``_v{N}`` counter (v2, v3, ...) so
    no real data is dropped and so slugs never embed raw I-codes. The
    ``column_mapper`` is the upstream source of truth; this is a local
    safety net, not a semantic change.

    Note (2026-05-27): the previous scheme used ``_s{sub_index}`` plus an
    I-code fallback (``{target}_{entry.code.lower()}``). The sub_index
    suffix gave no real discrimination outside spectrograms (almost every
    column has sub_index=1), and the I-code fallback embedded raw I-codes
    (e.g. ``suppression_left_i179_1``) which leak Persyst-internal indices
    into the user-facing schema. Position-based ``_v{N}`` avoids both.
    """
    code_to_entry: dict[str, ColumnEntry] = {e.code: e for e in schema}
    rename_map: dict[str, str] = {}
    slug_to_trend: dict[str, str] = {}
    slug_to_entry: dict[str, ColumnEntry] = {}
    used_slugs: set[str] = set()

    for col in df.columns:
        if col == "ClockDateTime":
            continue
        entry = code_to_entry.get(col)
        if entry is None or not entry.common_name:
            continue
        target = entry.common_name
        if target in used_slugs:
            # Position-based disambiguation: v2 for the second occurrence, v3 for
            # the third, and so on. Walks forward until a free slot is found so
            # that adjacent collisions remain stable across reprocesses.
            n = 2
            while f"{target}_v{n}" in used_slugs:
                n += 1
            target = f"{target}_v{n}"
        used_slugs.add(target)
        rename_map[col] = target
        slug_to_trend[target] = entry.trend_name
        slug_to_entry[target] = entry

    keep = ["ClockDateTime"] if "ClockDateTime" in df.columns else []
    keep += list(rename_map.keys())
    renamed = df[keep].rename(columns=rename_map).copy()
    return renamed, slug_to_trend, slug_to_entry


def _merge_semantic_column(
    name: str,
    contributions: list[tuple[int, pd.Series]],
    master_index: pd.Index,
) -> pd.Series:
    """Merge one semantic column across segments on a shared time index.

    ``contributions`` is a list of ``(segment_idx, series_indexed_by_time)``.
    The series with the highest non-NaN count wins; first-seen tiebreak.
    Remaining NaN cells are backfilled from the next-best contributor, etc.
    """
    ranked = sorted(
        contributions,
        key=lambda t: (-int(t[1].notna().sum()), t[0]),
    )
    # Reindex each contributor onto the master index, then combine_first
    # in rank order — first rank fills, later ranks fill remaining NaN.
    merged: pd.Series | None = None
    for _, s in ranked:
        aligned = s.reindex(master_index)
        merged = aligned if merged is None else merged.combine_first(aligned)
    if merged is None:
        return pd.Series(np.nan, index=master_index, name=name)
    merged.name = name
    return merged


def merge_segments_by_semantic_name(
    parsed_exports: list[ParsedExport],
    mmx: Optional[Any] = None,
) -> tuple[ParsedExport, list[ColumnEntry]]:
    """Merge multiple ParsedExport segments by semantic column name.

    Each segment's I-codes are resolved to ``common_name`` slugs (via the
    column_mapper). Segments are stitched on ``ClockDateTime``:

    - Disjoint time ranges → rows concatenate, no overlap.
    - Overlapping ranges (same ClockDateTime across segments) → values
      merge per semantic column, rank-ordered by non-NaN density.

    Returns
    -------
    merged_parsed : ParsedExport
        A ParsedExport whose DataFrame columns are ``ClockDateTime`` +
        semantic slugs, and whose ``code_to_description`` is keyed by slug.
    merged_schema : list[ColumnEntry]
        Pre-built schema aligned with the merged DataFrame (one entry per
        unique semantic name, ``code`` field = ``common_name``).
    """
    if not parsed_exports:
        raise ValueError("merge_segments_by_semantic_name: no segments provided")

    if len(parsed_exports) == 1:
        parsed = parsed_exports[0]
        schema = _build_schema(parsed.code_to_description, mmx)
        renamed_df, slug_to_trend, slug_to_entry = _rename_segment(parsed.data, schema)
        # Build schema aligned to slugs (one entry per slug, post-disambiguation)
        sem_schema: list[ColumnEntry] = [
            replace(entry, code=slug)
            for slug, entry in slug_to_entry.items()
        ]
        merged = ParsedExport(
            data=renamed_df,
            code_to_description=slug_to_trend,
            description_to_codes={
                trend: [name] for name, trend in slug_to_trend.items()
            },
            metadata=parsed.metadata,
            code_row_index=parsed.code_row_index,
            trend_row_index=parsed.trend_row_index,
        )
        return merged, sem_schema

    # Build per-segment: schema, renamed df, slug→trend, slug→entry
    per_seg: list[tuple[int, pd.DataFrame, list[ColumnEntry], dict[str, str], dict[str, ColumnEntry]]] = []
    for idx, p in enumerate(parsed_exports):
        schema = _build_schema(p.code_to_description, mmx)
        renamed, slug_to_trend, slug_to_entry = _rename_segment(p.data, schema)
        per_seg.append((idx, renamed, schema, slug_to_trend, slug_to_entry))

    # Build master time index = sorted union of all ClockDateTime values.
    # If any segment lacks ClockDateTime we fall back to a RangeIndex.
    have_clock = all("ClockDateTime" in df.columns for _, df, *_ in per_seg)
    if have_clock:
        all_clock = pd.concat(
            [df["ClockDateTime"] for _, df, *_ in per_seg], ignore_index=True
        )
        master_index = pd.Index(sorted(pd.unique(all_clock)), name="ClockDateTime")
    else:
        total_rows = sum(len(df) for _, df, *_ in per_seg)
        master_index = pd.RangeIndex(total_rows)

    def _indexed(df: pd.DataFrame, seg_idx: int) -> pd.DataFrame:
        if not have_clock:
            return df.reset_index(drop=True)
        dd = df.drop_duplicates(subset=["ClockDateTime"], keep="first")
        n_dropped = len(df) - len(dd)
        if n_dropped > 0:
            log.warning(
                "segment %d: dropped %d/%d rows with duplicate ClockDateTime "
                "during semantic merge (set_index needs unique timestamps)",
                seg_idx, n_dropped, len(df),
            )
        return dd.set_index("ClockDateTime", drop=True)

    indexed_segs: list[tuple[int, pd.DataFrame]] = []
    for seg_idx, df, _schema, _s2t, _s2e in per_seg:
        indexed_segs.append((seg_idx, _indexed(df, seg_idx)))

    # Gather contributions per slug
    contributions: dict[str, list[tuple[int, pd.Series]]] = {}
    for seg_idx, idx_df in indexed_segs:
        for slug in idx_df.columns:
            s = idx_df[slug]
            contributions.setdefault(slug, []).append((seg_idx, s))

    # Merge each slug into a single Series aligned to master_index
    merged_cols: dict[str, pd.Series] = {}
    for slug, contribs in contributions.items():
        merged_cols[slug] = _merge_semantic_column(slug, contribs, master_index)

    merged_df = pd.DataFrame(merged_cols, index=master_index)
    if have_clock:
        merged_df = merged_df.reset_index()  # ClockDateTime becomes a column
    else:
        merged_df = merged_df.reset_index(drop=True)

    # Build the merged code_to_description and schema from the winning
    # contributor per slug (highest non-NaN density; first-seen tiebreak).
    code_to_description: dict[str, str] = {}
    merged_schema: list[ColumnEntry] = []
    for slug, contribs in contributions.items():
        ranked = sorted(contribs, key=lambda t: (-int(t[1].notna().sum()), t[0]))
        winner_seg_idx = ranked[0][0]
        slug_to_trend_w = next(
            (s2t for seg_idx, _, _, s2t, _ in per_seg if seg_idx == winner_seg_idx),
            {},
        )
        slug_to_entry_w = next(
            (s2e for seg_idx, _, _, _, s2e in per_seg if seg_idx == winner_seg_idx),
            {},
        )
        code_to_description[slug] = slug_to_trend_w.get(slug, "")
        entry = slug_to_entry_w.get(slug)
        if entry is not None:
            merged_schema.append(replace(entry, code=slug))

    description_to_codes: dict[str, list[str]] = {}
    for slug, trend in code_to_description.items():
        description_to_codes.setdefault(trend, []).append(slug)

    merged_parsed = ParsedExport(
        data=merged_df,
        code_to_description=code_to_description,
        description_to_codes=description_to_codes,
        metadata=parsed_exports[0].metadata,
        code_row_index=parsed_exports[0].code_row_index,
        trend_row_index=parsed_exports[0].trend_row_index,
    )
    return merged_parsed, merged_schema
