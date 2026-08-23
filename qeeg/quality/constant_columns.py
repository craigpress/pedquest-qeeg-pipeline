"""Find columns that carried no information in this recording.

Two failure modes, both invisible in a summary statistic:

**Constant columns.** A column with one distinct value across the whole
recording has zero variance. It cannot correlate with an outcome, it cannot be
a covariate, and its mean is that constant rather than a measurement. The case
that motivated this: Persyst's `Status Epilepticus Advanced/Combined (Percent)`
trends sit at a **non-zero floor of 0.050331** when nothing is detected — they
never reach 0 — so a threshold of `> 0` fires on every epoch of every
recording, and a reported mean of "0.05%" is the floor, not a finding.

**Duplicate columns.** Two columns identical on every row are one variable
wearing two names. Entering both in a model is perfect collinearity; reporting
them as separate results double-counts. Persyst's `Advanced (Percent)` and
`Combined (Percent)` are byte-identical in every export examined.

Neither is a pipeline defect — both are faithfully transported vendor output.
They are reported so an analyst can see them before modelling, not repaired.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# Columns whose constancy is expected and uninformative to report: identifiers,
# flags and axes that are constant by construction.
_SKIP_PREFIXES = ("_", "patient_id", "ClockDateTime", "Time")


@dataclass
class ConstantColumnReport:
    """Zero-variance and duplicate columns found in one recording."""

    #: column -> the single value it held (NaN-only columns map to None)
    constant: dict[str, float | None] = field(default_factory=dict)
    #: columns that were entirely NaN — distinct from a constant measurement
    all_null: list[str] = field(default_factory=list)
    #: groups of columns identical on every row, each group sorted
    duplicate_groups: list[list[str]] = field(default_factory=list)
    n_checked: int = 0

    @property
    def n_constant(self) -> int:
        return len(self.constant)

    @property
    def n_duplicated(self) -> int:
        return sum(len(g) - 1 for g in self.duplicate_groups)

    def warnings(self) -> list[str]:
        out: list[str] = []
        if self.all_null:
            out.append(
                f"{len(self.all_null)} column(s) are entirely missing: "
                + ", ".join(sorted(self.all_null)[:5])
                + (" …" if len(self.all_null) > 5 else "")
            )
        nonzero_const = {c: v for c, v in self.constant.items() if v not in (0, None)}
        if nonzero_const:
            shown = ", ".join(f"{c}={v:g}" for c, v in
                              sorted(nonzero_const.items())[:4])
            out.append(
                f"{len(nonzero_const)} column(s) hold one non-zero value for the "
                f"whole recording — a floor, not a measurement: {shown}"
                + (" …" if len(nonzero_const) > 4 else "")
            )
        zero_const = [c for c, v in self.constant.items() if v == 0]
        if zero_const:
            out.append(
                f"{len(zero_const)} column(s) are zero for the whole recording: "
                + ", ".join(sorted(zero_const)[:5])
                + (" …" if len(zero_const) > 5 else "")
            )
        for g in self.duplicate_groups:
            out.append(
                "columns identical on every row — do not model them as "
                f"separate variables: {', '.join(g)}"
            )
        return out

    def to_dict(self) -> dict:
        return {
            "n_checked": self.n_checked,
            "n_constant": self.n_constant,
            "n_duplicated": self.n_duplicated,
            "constant": {k: (None if v is None else float(v))
                         for k, v in sorted(self.constant.items())},
            "all_null": sorted(self.all_null),
            "duplicate_groups": [sorted(g) for g in self.duplicate_groups],
        }


def find_constant_columns(df: pd.DataFrame,
                          *,
                          max_duplicate_scan: int = 4096) -> ConstantColumnReport:
    """Report zero-variance and duplicate numeric columns in *df*.

    NaN is treated as missing, not as a value: a column that is 5.0 wherever it
    is present is constant, whether or not some epochs were nulled. A column
    that is *entirely* NaN is reported separately — that is absence of data
    rather than a degenerate measurement.
    """
    rep = ConstantColumnReport()
    cols = [c for c in df.columns
            if not str(c).startswith(_SKIP_PREFIXES)
            and df[c].dtype.kind in "fiu"]
    rep.n_checked = len(cols)
    if not cols or len(df) < 2:
        return rep

    sub = df[cols]
    # min == max over non-null values identifies constants without the cost of
    # nunique() on a wide frame.
    mins = sub.min(numeric_only=True)
    maxs = sub.max(numeric_only=True)
    n_valid = sub.notna().sum()

    for c in cols:
        if n_valid.get(c, 0) == 0:
            rep.all_null.append(c)
            continue
        lo, hi = mins.get(c), maxs.get(c)
        if pd.notna(lo) and pd.notna(hi) and lo == hi:
            rep.constant[c] = float(lo)

    # Duplicates: group by a cheap signature first, then confirm exactly. Only
    # non-constant columns are worth comparing -- constants are already flagged,
    # and every all-zero column would otherwise form one huge useless group.
    varying = [c for c in cols if c not in rep.constant and c not in rep.all_null]
    if len(varying) > max_duplicate_scan:
        varying = varying[:max_duplicate_scan]

    buckets: dict[tuple, list[str]] = {}
    for c in varying:
        s = sub[c]
        sig = (round(float(s.min()), 9), round(float(s.max()), 9),
               int(s.notna().sum()), round(float(np.nansum(s.values)), 6))
        buckets.setdefault(sig, []).append(c)

    for group in buckets.values():
        if len(group) < 2:
            continue
        # Confirm exactly; a signature collision is possible.
        remaining = list(group)
        while len(remaining) > 1:
            head, rest = remaining[0], remaining[1:]
            same = [head]
            for other in rest:
                if sub[head].equals(sub[other]):
                    same.append(other)
            if len(same) > 1:
                rep.duplicate_groups.append(sorted(same))
            remaining = [c for c in rest if c not in same]

    return rep
