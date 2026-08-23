"""The published column maps must stay usable as identifier references.

`docs/COLUMN_MAP_V10_*` are what an analyst reads to find a column. Two
properties have to hold or the map misleads rather than helps:

  * every `variable_name` is unique within its panel, and
  * none of them is a `__dupN` uniqueness-backstop name.

The backstop exists so ingestion never silently drops a column, but a name
like `seizure_detection_event__dup2` tells a reader only "some other
detection column" — the instrument it belongs to is exactly the thing the
suffix hides. Any occurrence is a naming bug in `generate_common_name`.
"""
import csv
from pathlib import Path

import pytest

_DOCS = Path(__file__).resolve().parent.parent / "docs"
_MAPS = sorted(_DOCS.glob("COLUMN_MAP_V10_*.csv"))


def test_column_maps_are_present():
    assert _MAPS, "no COLUMN_MAP_V10_*.csv found in docs/"


@pytest.mark.parametrize("path", _MAPS, ids=lambda p: p.stem)
def test_no_uniqueness_backstop_names(path):
    with path.open(encoding="utf-8") as fh:
        offenders = [r["variable_name"] for r in csv.DictReader(fh)
                     if "__dup" in r["variable_name"]]
    assert not offenders, (
        f"{path.name} publishes {len(offenders)} backstop name(s): "
        f"{offenders[:5]}. Give the instruments distinct names in "
        f"generate_common_name instead."
    )


@pytest.mark.parametrize("path", _MAPS, ids=lambda p: p.stem)
def test_variable_names_are_unique(path):
    with path.open(encoding="utf-8") as fh:
        names = [r["variable_name"] for r in csv.DictReader(fh) if r["variable_name"]]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"{path.name} has duplicate variable_name(s): {sorted(dupes)[:5]}"


@pytest.mark.parametrize("path", _MAPS, ids=lambda p: p.stem)
def test_variable_names_are_valid_identifiers(path):
    """Names are used directly as R / Python / SQL column identifiers."""
    with path.open(encoding="utf-8") as fh:
        bad = [r["variable_name"] for r in csv.DictReader(fh)
               if r["variable_name"] and not r["variable_name"].isidentifier()]
    assert not bad, f"{path.name} has non-identifier variable_name(s): {bad[:5]}"


# ---------------------------------------------------------------------------
# The maps are published artifacts — to a second repository, and potentially
# onward to collaborators. They are generated from a real patient export, so
# the generator must not carry the source path into them: the parent directory
# of an export is the subject/recording identifier.
# ---------------------------------------------------------------------------

_ID_PATTERNS = (
    r"\b4290[-_]\d+",      # study subject IDs in this cohort
    r"cardiac_arrest",         # the share the exports live on
    # A drive-letter path into somewhere real data lives. Deliberately not
    # a bare `X:/` — that also matches the `s:/` inside `https://`.
    r"[A-Za-z]:[\\/](?:temp|Temp|Users|data)[\\/]",
    r"\\\\[A-Za-z0-9_.-]+\\",   # UNC share
    r"PatientID",
    r"BirthDate",
)


@pytest.mark.parametrize("path", sorted(_DOCS.glob("COLUMN_MAP_V10_*")),
                         ids=lambda p: p.name)
def test_no_subject_identifiers_or_paths(path):
    """Provenance records which export, never whose."""
    import re
    text = path.read_text(encoding="utf-8", errors="replace")
    hits = {p: re.findall(p, text)[:3] for p in _ID_PATTERNS
            if re.search(p, text)}
    assert not hits, (
        f"{path.name} carries subject-identifying content: {hits}. "
        f"gen_column_map_v10.py records only the export's basename — check it "
        f"has not regained the full path."
    )
