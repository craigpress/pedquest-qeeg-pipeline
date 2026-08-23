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
