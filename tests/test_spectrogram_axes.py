"""Every spectrogram spec_type must resolve its frequency axis from the schema.

`get_spectrogram_data` looks the schema family up by spec_type and falls back to
`freq_min + (k-1) * resolution` when the lookup misses. The fallback is a
different formula from every schema's own, so a missing key does not raise — it
silently returns a plausible-looking axis that is wrong.

That is what happened to the bare ``asymmetry`` spec_type: it fell through to
family ``asymmetry``, which is not a schema key, and produced 0.00..19.50 Hz
instead of the schema's 0.50..20.00. Each bin was labelled half a bin low and
the 20 Hz bin fell off the end.
"""
import pytest

from api.services.pipeline_service import PipelineService
from qeeg.ingestion.subcol_schema import SCHEMAS, get_spectrogram_bin_freq

# spec_type -> (schema family, bins, first bin Hz, last bin Hz)
EXPECTED = {
    "fft_left":          ("fft_spectrogram",       40, 0.5, 20.0),
    "fft_right":         ("fft_spectrogram",       40, 0.5, 20.0),
    "asymmetry":         ("asymmetry_spectrogram", 40, 0.5, 20.0),
    "asymmetry_hemi":    ("asymmetry_spectrogram", 40, 0.5, 20.0),
    "asymmetry_ant":     ("asymmetry_spectrogram", 40, 0.5, 20.0),
    "asymmetry_post":    ("asymmetry_spectrogram", 40, 0.5, 20.0),
    "asymmetry_temp":    ("asymmetry_spectrogram", 40, 0.5, 20.0),
    "asymmetry_parasag": ("asymmetry_spectrogram", 40, 0.5, 20.0),
    "rhythmicity":       ("rhythmicity_spectrogram", 97, 1.0, 25.0),
    "coherence":         ("coherence_spectrogram",   63, 0.0, 32.0),
}


def _schema_map() -> dict[str, str]:
    """The spec_type -> schema-family table, read from the source of truth."""
    import inspect
    import re
    src = inspect.getsource(PipelineService.get_spectrogram_data)
    block = re.search(r"_schema_family_for_spec_type = \{(.*?)\}", src, re.S)
    assert block, "could not locate _schema_family_for_spec_type"
    return dict(re.findall(r'"([\w]+)":\s*"([\w]+)"', block.group(1)))


@pytest.mark.parametrize("spec_type", sorted(EXPECTED))
def test_spec_type_maps_to_a_real_schema(spec_type):
    """A missing key degrades to a wrong axis rather than an error."""
    mapping = _schema_map()
    assert spec_type in mapping, (
        f"{spec_type!r} is absent from _schema_family_for_spec_type, so its axis "
        f"will come from the (k-1)*resolution fallback instead of the schema."
    )
    family = mapping[spec_type]
    assert family in SCHEMAS, f"{spec_type!r} maps to unknown schema {family!r}"


@pytest.mark.parametrize("spec_type", sorted(EXPECTED))
def test_axis_endpoints_match_the_schema_formula(spec_type):
    family, n_bins, first, last = EXPECTED[spec_type]
    assert SCHEMAS[family].expected_count == n_bins
    assert get_spectrogram_bin_freq(family, 1) == pytest.approx(first)
    assert get_spectrogram_bin_freq(family, n_bins) == pytest.approx(last)


def test_fallback_and_schema_disagree_for_the_linear_families():
    """Why a missing key is dangerous rather than merely untidy.

    If the two formulas agreed, a missing key would be harmless. They do not:
    for the 0.5 Hz families the fallback is exactly one half-bin low.
    """
    schema_first = get_spectrogram_bin_freq("fft_spectrogram", 1)
    fallback_first = 0.0 + (1 - 1) * 0.5
    assert schema_first != fallback_first
    assert schema_first - fallback_first == pytest.approx(0.5)
