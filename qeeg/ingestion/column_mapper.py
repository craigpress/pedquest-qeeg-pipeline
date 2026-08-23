"""Map Persyst CSV I-code columns to semantic meaning."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from qeeg.ingestion.mmx_parser import MMXConfig

logger = logging.getLogger(__name__)

from qeeg.constants import (
    ASYMMETRY_BANDS,
    ASYMMETRY_REGIONS,
    ELECTRODE_NAME_MAP,
    FEATURE_FAMILIES,
    FREQUENCY_BANDS,
    I_GROUP_SUBCOLUMN_NAMES,
    SPECTROGRAM_FREQ_MAP,
)

# ---------------------------------------------------------------------------
# Electrode names used in Persyst trend descriptions
# ---------------------------------------------------------------------------
_ELECTRODE_NAMES: list[str] = [
    "Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4",
    "O1", "O2", "F7", "F8", "T3", "T4", "T5", "T6",
    "Fz", "Cz", "Pz", "A1", "A2",
    "P7", "P8", "T7", "T8", "F9", "F10",
]

# Regex for normalizing old 10-20 electrode names in trend descriptions.
# Matches whole-word boundaries to avoid false positives (e.g. "T3" in "T30").
_OLD_ELECTRODE_RE = re.compile(
    r"\b(" + "|".join(re.escape(old) for old in ELECTRODE_NAME_MAP) + r")\b"
)


def normalize_electrode_names(trend_name: str) -> str:
    """Replace old 10-20 electrode names (T3/T4/T5/T6) with current standard (T7/T8/P7/P8)."""
    return _OLD_ELECTRODE_RE.sub(lambda m: ELECTRODE_NAME_MAP[m.group(0)], trend_name)


# Electrode chain pattern: one or more electrode names concatenated (e.g. F3C3P3,
# FP1-F3, Fz-Cz). Case-insensitive so raw Persyst exports with all-caps tokens
# like "FP1" match the sorted list (which stores "Fp1"). We also tolerate a
# single hyphen or dash between chain segments for multi-pair derivations.
_ELECTRODE_PATTERN = re.compile(
    r"(?:"
    + "|".join(re.escape(e) for e in sorted(_ELECTRODE_NAMES, key=len, reverse=True))
    + r")(?:-?(?:"
    + "|".join(re.escape(e) for e in sorted(_ELECTRODE_NAMES, key=len, reverse=True))
    + r"))*",
    re.IGNORECASE,
)

# Electrode chain → brain region mapping
ELECTRODE_CHAIN_REGIONS: dict[str, tuple[str, str]] = {
    # (hemisphere, region_description)
    "F3C3P3":   ("left",  "frontal_central_parietal"),
    "F4C4P4":   ("right", "frontal_central_parietal"),
    "P3P7O1":   ("left",  "parietal_temporal_occipital"),
    "P4P8O2":   ("right", "parietal_temporal_occipital"),
    "F7T3P7":   ("left",  "fronto_temporal_parietal"),
    "F8T4P8":   ("right", "fronto_temporal_parietal"),
    "F7T7P7":   ("left",  "fronto_temporal_parietal"),   # normalized from F7T3P7
    "F8T8P8":   ("right", "fronto_temporal_parietal"),   # normalized from F8T4P8
    "T3T5O1":   ("left",  "temporal_occipital"),
    "T4T6O2":   ("right", "temporal_occipital"),
    "T7P7O1":   ("left",  "temporal_occipital"),         # normalized from T3T5O1
    "T8P8O2":   ("right", "temporal_occipital"),         # normalized from T4T6O2
    "C3P3O1":   ("left",  "central_parietal_occipital"),
    "C4P4O2":   ("right", "central_parietal_occipital"),
    "Fp1F3C3":  ("left",  "frontal"),
    "Fp2F4C4":  ("right", "frontal"),
}


# ---------------------------------------------------------------------------
# Spectrogram frequency label helper
# ---------------------------------------------------------------------------

# Maps column_mapper family names to canonical schema family slugs.
# The schema is the single source of truth for sub-col counts AND bin-frequency
# formulae — see qeeg.ingestion.subcol_schema and PersystTrendCSV_Format_Reference.md §3.
_SPEC_FAMILY_MAP = {
    "fft_spectrogram":       "fft_spectrogram",
    "asymmetry":             "asymmetry_spectrogram",
    "rhythmicity":           "rhythmicity_spectrogram",
    "coherence_spectrogram": "coherence_spectrogram",
}

# The MMX parser infers its own family vocabulary (mmx_parser._infer_family) which
# is NOT the same as classify_family's. Where they disagree, the MMX name is the
# *schema* slug while this module's branches key off the shorter mapper name — so
# an unmapped MMX family silently misses every spectrogram branch, loses its
# bin-centre frequency, and lands in the generic fallback below, which embeds the
# volatile I-code in the identifier. Normalise at the boundary instead.
#
# Covers 58 instruments in the V8 Research panel: 50 rhythmicity + 8 asymmetry.
_MMX_FAMILY_ALIASES = {
    "rhythmicity_spectrogram": "rhythmicity",
    "asymmetry_spectrogram":   "asymmetry",
}


def canonical_family(family: str) -> str:
    """Map an MMX-inferred family name onto this module's family vocabulary."""
    return _MMX_FAMILY_ALIASES.get(family, family)


# Rhythmicity FreqPow: 16 sub-columns = 4 bands x 4 values per band, per
# PersystTrendCSV_Format_Reference.md §3.27. Band edges follow Persyst's
# Rhythmicity help page ("four bands: 1-4 Hz, 4-9 Hz, 9-16 Hz and 16-25 Hz"),
# which the exported data supports.
_RHYTHMICITY_FREQPOW_BANDS = ("1_4hz", "4_9hz", "9_16hz", "16_25hz")

# Position within each 4-column block, per Persyst (Mike, email to C. Press,
# 2026-08-21). Positions 1 and 3 were already confirmed against the §3.25
# SumValues scalars; 2 and 4 were previously carried as positional placeholders
# ("v2"/"v4") and are now named. Keep in lockstep with
# qeeg.ingestion.subcol_schema.RHYTHMICITY_FREQPOW.
_RHYTHMICITY_FREQPOW_POSITIONS = ("freq", "bandwidth", "power", "fraction")


def _spectrogram_freq_label(family: str, sub_index: int) -> str:
    """Return the spectrogram bin's center-frequency slug (e.g. ``'9_00hz'``).

    The decimal point is written as ``_`` so the slug is a safe identifier
    everywhere the export lands: a ``.`` in a column name is mangled by R's
    ``data.frame``, needs quoting in SQL, and trips some parquet consumers.
    Two decimal places is enough to keep every bin distinct in all four
    spectrogram families (verified: FFT 40, asymmetry 40, coherence 63,
    rhythmicity 97 — no collisions).

    Delegates to qeeg.ingestion.subcol_schema.get_spectrogram_bin_freq, which
    encodes the correct formula per family:
      * FFT, Asymmetry: linear, ``f_k = k × 0.5`` Hz (0.5–20 Hz, 40 bins)
      * Coherence:      linear, ``f_k = (k-1) × 32/62`` Hz (0–32 Hz, 63 bins)
      * Rhythmicity:    SQRT,   ``f_k = (1 + (k-1)/24)²`` Hz (1–25 Hz, 97 bins)

    Returns the raw index string for unknown families or out-of-range bins.
    """
    from qeeg.ingestion.subcol_schema import get_spectrogram_bin_freq
    spec_key = _SPEC_FAMILY_MAP.get(family)
    if not spec_key:
        return str(sub_index)
    freq = get_spectrogram_bin_freq(spec_key, sub_index)
    if freq is None:
        return str(sub_index)
    return f"{freq:.2f}".replace(".", "_") + "hz"


@dataclass
class ColumnEntry:
    col_index: int
    code: str               # "I4_1"
    i_group: int            # 4
    sub_index: int          # 1
    trend_name: str         # "FFT Power, 1 - 4 Hz, Left Hemisphere"
    family: str             # "fft_power" | "artifact_intensity" | ...
    frequency_band: str     # "delta" | "theta" | "alpha" | "beta" | "gamma" | ""
    freq_min_hz: Optional[float]    # 1.0
    freq_max_hz: Optional[float]    # 4.0
    hemisphere: str         # "left" | "right" | ""
    region: str             # "anterior" | "posterior" | "hemisphere" | ""
    electrode: str          # "Fp1" | "F3C3P3" | ""
    # ---- new fields ----
    sub_column_name: str = field(default="")
    # sub_column_name: electrode name (artifact), BSS component, RDA laterality, etc.
    common_name: str = field(default="")
    # common_name: machine-readable label combining family + band + region + electrode.
    # Valid Python/R identifier (lowercase, underscores).  Used in exports.
    source_code: str = field(default="")
    # The original Persyst I-code, kept when `code` is replaced by the semantic
    # slug so provenance (original_code in the data dictionary) survives the
    # rename.

    mmx_name: str = field(default="")
    # The resolved MMX instrument's Name. Needed at naming time for anything the
    # display label does not carry: Persyst does not update the label when a
    # trend's averaging window changes, so the window is only in the MMX.

    resolution: str = field(default="")
    # How this column's identity was established:
    #   "ordinal" — panel position (authoritative; the only method that can
    #               separate instruments Persyst ships under one display label)
    #   "name"    — exact trend-name match against mmx.instruments (~0.3% hit rate)
    #   "regex"   — no MMX match; classified from the trend name alone
    #   "tail"    — the trailing Comment/Time pseudo-columns, which have no
    #               instrument by design
    # Exports record the mix so a dataset states how its columns were resolved
    # rather than implying ordinal resolution was used when it was not.


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

# A numeric band ratio such as "8-13/1-30" appearing anywhere in a trend name.
_RATIO_IN_NAME = re.compile(r"\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?")


# Left/right 10-20 electrodes as they appear inside Persyst EventDensity
# expressions. Odd numbers are left, even are right; both old (T3/T5) and current
# (T7/P7) names occur.
_SPIKE_LEFT = ("Fp1", "FP1", "F3", "F7", "C3", "T3", "T7", "P3", "T5", "P7", "O1")
_SPIKE_RIGHT = ("Fp2", "FP2", "F4", "F8", "C4", "T4", "T8", "P4", "T6", "P8", "O2")


def _spike_laterality(mmx_name: str) -> str:
    """Derive spike-detector laterality from the electrodes in its expression.

    Returns ``"left"``, ``"right"``, ``"generalized"`` or ``""``. A SpikeGen
    detector, or a mix of both sides, is generalized.
    """
    if "SpikeGen" in mmx_name:
        return "generalized"
    # Persyst builds the one-sided detectors as "[this side] AND NOT[other side]",
    # and the bilateral one as a plain "[left] AND [right]". So drop only the
    # negated clause and score what remains -- exactly what the rhythmic-delta
    # branch below does with the same vendor pattern.
    #
    # Splitting on " AND " unconditionally (the previous rule) made the
    # `has_l and has_r -> generalized` test below unreachable for every compound
    # expression, which is the only shape that can reach it. I166, a bilateral
    # detector, came out as "left".
    if "AND NOT[" in mmx_name:
        mmx_name = mmx_name.split("AND NOT[", 1)[0]
    has_l = any(re.search(r"\b" + e + r"\b", mmx_name) for e in _SPIKE_LEFT)
    has_r = any(re.search(r"\b" + e + r"\b", mmx_name) for e in _SPIKE_RIGHT)
    if has_l and has_r:
        # Both electrode sets required, i.e. both hemispheres concurrently
        # positive. Distinct from Persyst's SpikeGen detector above, which is a
        # generalized-spike detector in its own right -- so this is "bilateral",
        # not "generalized". Keeping them separate also stops I166 (L AND R) and
        # I169 (SpikeGen) collapsing onto one identifier.
        return "bilateral"
    if has_l:
        return "left"
    if has_r:
        return "right"
    return ""


def classify_family(trend_name: str) -> str:
    """Classify a trend name into a feature family using FEATURE_FAMILIES patterns.

    Patterns are checked in definition order; the first match wins.
    Returns ``"other"`` when no pattern matches.
    """
    # Power ratios need denominator-aware classification — the numerator alone
    # cannot distinguish relative power (band/1-30) from ADR (8-13/1-4) or
    # RAV (6-14/1-20). Route every PowerRatio trend through classify_ratio.
    #
    # Match on the ratio itself, not just the literal "FFT PowerRatio" label:
    # Persyst also ships these under descriptive names such as
    # "Relative Alpha, 8-13/1-30 Hz". Keying on the label alone sent those down
    # the keyword path and classified alpha-over-broadband — a relative POWER
    # measure — as alpha_variability, i.e. RAV, which is 6-14/1-20. The
    # denominator is authoritative; see classify_ratio.
    # Run the keyword pass first, then re-route only if it landed somewhere a
    # power ratio could plausibly belong. Routing on the ratio alone stole any
    # trend whose label happens to carry an "N-N/N-N" substring -- an aEEG,
    # suppression-ratio or SEF label with a band ratio in it would have been
    # classified relative_power and picked up a (0,1) range guard and
    # "fraction" units it has no business with.
    _kw = None
    for _family, _pattern in FEATURE_FAMILIES.items():
        if re.search(_pattern, trend_name):
            _kw = _family
            break

    _POWERISH = {"fft_power", "fft_power_ratio", "alpha_variability", "adr",
                 "relative_power", None}
    if (re.search(r"FFT[_ ]PowerRatio", trend_name)
            or (_RATIO_IN_NAME.search(trend_name) and _kw in _POWERISH)):
        family, _ = classify_ratio(trend_name)
        if family != "fft_power_ratio":
            return family
    if _kw is not None:
        return _kw
    for family, pattern in FEATURE_FAMILIES.items():
        if re.search(pattern, trend_name):
            return family
    return "other"


def extract_frequency_range(trend_name: str) -> tuple[Optional[float], Optional[float]]:
    """Parse Hz ranges from a trend name.

    Handles:
    - ``"1 - 4 Hz"``         -> (1.0, 4.0)
    - ``"8-13/1-4 Hz"``      -> (8.0, 13.0)   # numerator only
    - ``"6-14/1-20 Hz"``     -> (6.0, 14.0)
    - ``"2 - 20 Hz"``        -> (2.0, 20.0)

    Returns ``(None, None)`` when no frequency information is found.
    """
    # Ratio pattern: numerator/denominator Hz  (take numerator only)
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*/\s*\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?\s*Hz",
        trend_name,
    )
    if m:
        return float(m.group(1)), float(m.group(2))

    # Simple range: min - max Hz
    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*Hz", trend_name)
    if m:
        return float(m.group(1)), float(m.group(2))

    return None, None


# Ratio-denominator → metric-type map. The denominator band determines the
# *kind* of power ratio, which Persyst encodes only implicitly:
#   //1-4   → band-vs-delta ratio   (ADR = 8-13/1-4, TDR = 4-8/1-4)
#   //1-20  → relative alpha var.   (RAV = 6-14/1-20)
#   //1-30  → relative band power   (band / total 1-30 Hz broadband)
# Added 2026-06-10 for V8 MMX, which introduced the //1-30 relative-power set.
_RATIO_DELTA_DENOM = (1.0, 4.0)
_RATIO_RAV_DENOM = (1.0, 20.0)
_RATIO_RELPOWER_DENOM = (1.0, 30.0)


def extract_ratio_bands(
    trend_name: str,
) -> tuple[Optional[tuple[float, float]], Optional[tuple[float, float]]]:
    """Parse both numerator and denominator of a Persyst power-ratio trend.

    Handles the CSV form ``"FFT PowerRatio, 8-13/1-4 Hz, …"`` (single slash) and
    the MMX form ``"FFT_PowerRatio 8-13//1-30 …"`` (double slash).

    Returns ``((num_lo, num_hi), (den_lo, den_hi))`` or ``(None, None)`` when the
    trend is not a ratio.
    """
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*/+\s*"
        r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)",
        trend_name,
    )
    if not m:
        return None, None
    num = (float(m.group(1)), float(m.group(2)))
    den = (float(m.group(3)), float(m.group(4)))
    return num, den


def _denoms_match(den: tuple[float, float], target: tuple[float, float]) -> bool:
    """Tolerant equality for a ratio denominator band (handles 13-20 vs 13-30 etc.)."""
    return abs(den[0] - target[0]) < 0.51 and abs(den[1] - target[1]) < 0.51


def classify_ratio(trend_name: str) -> tuple[str, str]:
    """Classify a power-ratio trend into (family, band-or-kind) by its denominator.

    Returns:
        (family, descriptor) where family is one of
        ``"relative_power" | "adr" | "alpha_variability" | "fft_power_ratio"``
        and descriptor is the numerator band name (relative_power) or the
        ratio kind ("adr" / "tdr" / "rav" / "") for the others.

    The denominator is authoritative:
        //1-30 → relative_power, descriptor = numerator band (delta/theta/alpha/beta)
        //1-20 → alpha_variability (RAV)
        //1-4  → adr family; 8-13 numerator = ADR, 4-8 numerator = TDR
    """
    num, den = extract_ratio_bands(trend_name)
    if num is None or den is None:
        return "fft_power_ratio", ""

    if _denoms_match(den, _RATIO_RELPOWER_DENOM):
        band = map_to_band(num[0], num[1])
        return "relative_power", band or "broadband"
    if _denoms_match(den, _RATIO_RAV_DENOM):
        return "alpha_variability", "rav"
    if _denoms_match(den, _RATIO_DELTA_DENOM):
        # band-vs-delta ratio: 8-13/1-4 = ADR, 4-8/1-4 = TDR
        if abs(num[0] - 8.0) < 0.51:
            return "adr", "adr"
        if abs(num[0] - 4.0) < 0.51:
            return "adr", "tdr"
        return "adr", "adr"
    # Unknown denominator — keep as generic ratio
    return "fft_power_ratio", ""


def map_to_band(
    freq_min: float,
    freq_max: float,
    bands: dict[str, tuple[float, float]] | None = None,
) -> str:
    """Map a frequency range to a named band.

    A match occurs when the query range exactly equals or is fully contained
    within a defined band.  Returns ``""`` when no band matches.
    """
    if bands is None:
        bands = FREQUENCY_BANDS

    for band_name, (band_lo, band_hi) in bands.items():
        if freq_min >= band_lo and freq_max <= band_hi:
            return band_name
    return ""


def _trend_tail(trend_name: str) -> str:
    """Return the last comma-separated segment of a Persyst trend name.

    Persyst CSV headers follow the pattern ``"<GraphTitle>, <Engine>, <Band>,
    <Channels>"`` where ``<Channels>`` (the last segment) is the authoritative
    region/hemisphere/electrode for the specific instrument. The preamble
    often contains decorative text that mentions both sides of an L/R pair
    (e.g. ``"Left Hemisphere (Blue) Right Hemisphere (Red)"``), so scanning
    the whole string yields false matches. Return the tail so the extractors
    can parse the authoritative token first.
    """
    return trend_name.rsplit(",", 1)[-1].strip() if "," in trend_name else trend_name


def extract_hemisphere(trend_name: str) -> str:
    """Return ``"left"``, ``"right"``, or ``""`` based on the trend name.

    Parses the trend-name tail first (authoritative region per Persyst
    convention), falls back to whole-string match for legacy trend names
    without a comma-separated tail.
    """
    tail = _trend_tail(trend_name)
    if "Left" in tail:
        return "left"
    if "Right" in tail:
        return "right"
    # Legacy fallback — some trends encode the hemisphere only in the preamble.
    if "Left" in trend_name:
        return "left"
    if "Right" in trend_name:
        return "right"
    return ""


def extract_region(trend_name: str) -> str:
    """Return ``"anterior"``, ``"posterior"``, ``"hemisphere"``, or ``""``.

    Tail-first parse mirrors :func:`extract_hemisphere` to keep both axes
    aligned on the same authoritative token.
    """
    tail = _trend_tail(trend_name)
    if "Anterior" in tail:
        return "anterior"
    if "Posterior" in tail:
        return "posterior"
    if "Hemisphere" in tail:
        return "hemisphere"
    # Legacy fallback.
    if "Anterior" in trend_name:
        return "anterior"
    if "Posterior" in trend_name:
        return "posterior"
    if "Hemisphere" in trend_name:
        return "hemisphere"
    return ""


def extract_electrode(trend_name: str) -> str:
    """Extract electrode name or chain from a trend name.

    Returns the authoritative electrode chain from the tail segment
    (e.g. ``"Fp1"``, ``"F3C3P3"``, ``"FP1-F3"``). Persyst display-overlay
    pairs put a dot-prefixed chain in the tail (``".F4C4P4"``) to mark the
    right-side overlay — we strip the dot so the chain matches downstream.
    Falls back to the whole string for legacy trends without a tail.
    """
    tail = _trend_tail(trend_name)
    # Strip the Persyst dot-prefix overlay marker (e.g. ".F4C4P4" → "F4C4P4").
    tail_clean = tail.lstrip(".")
    m = _ELECTRODE_PATTERN.search(tail_clean)
    if m:
        # Preserve source case; strip hyphens so chain names like "FP1-F3"
        # produce a single token ("FP1F3") distinct from "F3-C3" ("F3C3").
        return m.group(0).replace("-", "")
    m = _ELECTRODE_PATTERN.search(trend_name)
    return m.group(0).replace("-", "") if m else ""


def get_subcolumn_name(i_group: int, sub_index: int, trend_name: str, family: str,
                       mmx_name: str | None = None) -> str:
    """Return a specific identity label for this sub-column.

    Resolution order (MMX-version-independent):

    1. **Family-keyed schema** — for multi-sub-col instrument families with a
       fixed sub-col layout (artifact_intensity, artifact_detector,
       electrode_quality, aeeg, seizure_detection_notif_pair,
       rhythmicity_freqpow), look up the slug by family + sub-col position.
       This works the same way across all MMX versions (V3 through V7+).

    2. **Legacy I-group keyed table** — for I-groups whose sub-cols have V7-
       specific layout assumptions baked in (RDA, seizure event sub-cols,
       sleep stage display panels, spike-density rate variants) the
       ``I_GROUP_SUBCOLUMN_NAMES`` table is consulted as a fallback. These
       entries are V7-specific by design; files from other MMX versions will
       fall through to the trend-name-driven inferences below.

    3. **Trend-name parsing** — for families where the sub-col identity is
       encoded in the trend name (spike laterality, FFT band+region, etc.)
       parse it from the name.
    """
    # 1b. MMX-derived identity. When the instrument resolved by panel ordinal its
    #     name disambiguates sub-columns the display label cannot. Persyst exports
    #     all six sleep stages under the identical label "SleepStages"; only the
    #     instrument expression "= N <0> [SleepStages]" says which stage it is.
    #     Without this all seven collapse onto one identifier and the stage is
    #     unrecoverable downstream.
    if mmx_name:
        if family == "sleep":
            m = re.match(r"=\s*(\d+)\s*<", mmx_name.strip())
            if m:
                return f"stage_{m.group(1)}"
            # "Sleep-Wake State" is a separate trend from "SleepStages"; both
            # otherwise reduce to the same slug.
            if "sleep-wake" in trend_name.lower():
                return "wake_state"

        if family == "seizure_probability":
            # I144 and I145 share one display label, "Seizure probability (black)
            # and detections (red...)". The MMX name carries the distinction.
            #
            # Match the suffix with a regex, not rsplit(" ")[-1]: Persyst wraps
            # derived channels as "Time Max <0,120> [SeizureProbabilityP14
            # Detections]", where the trailing bracket defeated the plain split.
            # That fell through to the bare `seizure_probability_p14` -- the
            # identifier v1 datasets used for the continuous score -- so a
            # detections-derived channel silently took the probability name.
            m_sfx = re.search(r"\b(Probability|Detections)\]?\s*$", mmx_name)
            if m_sfx:
                sub = m_sfx.group(1).lower()
                # A running Max/Avg/Min over an instrument is a different column
                # from the instrument, and must never share its identifier.
                m_win = re.search(r"\bTime\s+(Max|Avg|Min)\s*<\s*\d+\s*,\s*(\d+)\s*>", mmx_name)
                if m_win:
                    return f"{sub}_{m_win.group(1).lower()}{m_win.group(2)}s"
                return sub

        if family == "spike_density":
            # Laterality comes from the electrode set in the expression, not the
            # label: I166 and I167 both read "Spikes >=3 per ten seconds
            # (blue=left, red=right, yellow=L&R)" while their expressions select
            # F3/Fp1... and F4/Fp2... respectively. Both were named spike_left.
            # Only override when the label cannot settle it: these trends carry a
            # colour legend ("blue=left, red=right") mentioning both sides, so the
            # usual trend-name parsing picks the first and mislabels the rest.
            # The expression is the reliable source. extract_hemisphere() misses
            # the "right hemisphere >=3 per 10 sec" phrasing these labels use, so
            # laterality was dropped entirely and I163/I165 -- a genuine
            # right/left pair -- collided on spike_threshold_per_10s.
            lat = _spike_laterality(mmx_name)
            if lat:
                # Three shapes ship under near-identical prose:
                #   EventDensity ...                    the rate itself
                #   >= N <0> [EventDensity ...]         a threshold test
                #   [>= N ...] AND [...]                a compound indicator
                if " AND " in mmx_name:
                    # Laterality now separates these (bilateral vs generalized vs
                    # one-sided), so the display legend is no longer needed to tell
                    # the indicator variants apart.
                    kind = "indicator"
                elif ">=" in mmx_name:
                    kind = "threshold"
                else:
                    kind = "rate"
                return lat if kind == "rate" else f"{lat}_{kind}"

        if family == "rda":
            # All three rhythmic-delta channels ship under one display label,
            # "Rhythmic delta indicator (blue=left, red=right, green=gen)", so
            # laterality is recoverable only from the boolean expression:
            #     Left AND Right        -> generalized
            #     Left AND NOT[Right]   -> left
            #     Right AND NOT[Left]   -> right
            # Without this all three collapse onto rda_left, which is wrong for
            # two of them.
            if "AND NOT[" in mmx_name:
                head = mmx_name.split("AND NOT[", 1)[0]
                has_l, has_r = "Left" in head, "Right" in head
                if has_l and not has_r:
                    return "left"
                if has_r and not has_l:
                    return "right"
            elif "Left" in mmx_name and "Right" in mmx_name:
                # "bilateral", NOT "generalized". Persyst (Mike, 2026-08-21):
                # this channel fires when both hemispheres independently cross
                # the delta frequency and power thresholds in the same 1-second
                # epoch. There is no synchrony test — left and right
                # autocorrelations are computed independently, phase coherence
                # is not tested, amplitude symmetry is not tested, and the two
                # sides need not share a frequency. ACNS 2021 GRDA requires
                # bilateral synchrony, so this may be reported as "bilateral"
                # but never as GRDA. Craig renamed the V10 trend to match.
                return "bilateral"
            # Expression present but unreadable: return nothing rather than
            # falling through to the keyword scan below, which tests "left"
            # first against a label that literally reads
            # "(blue=left, red=right, green=gen)" and so labels every
            # unresolved rhythmic-delta channel "left" -- the original bug,
            # surviving as a fallback. Returning "" lets the uniqueness
            # backstop surface it visibly instead.
            return ""

    # 1. Family-keyed schema (MMX-version-independent)
    from qeeg.ingestion.subcol_schema import get_subcol_slug as _schema_subcol
    _family_alias = {
        # Map column_mapper family slug -> subcol_schema family slug.
        # The two are mostly identical; spell out the few that differ.
        "asymmetry":                 "asymmetry_spectrogram",   # only when sub-col
                                                                 # comes from spectrogram
        "rhythmicity":               "rhythmicity_spectrogram", # likewise
        "coherence_spectrogram":     "coherence_spectrogram",
        "electrode_quality":         "electrode_signal_quality",
        # SeizureEventsP14 exports two sub-columns, detection and notification.
        # classify_family returns "seizure_detection", which reached no schema,
        # so once the V7 I-group table stopped firing nothing named sub-column 2
        # and the pair fell to the uniqueness backstop as
        # seizure_detection / seizure_detection__dup2 -- which reads as "a second
        # detection column" when it is the notification channel.
        "seizure_detection":         "seizure_detection_notif_pair",
    }
    schema_family = _family_alias.get(family, family)
    schema_slug = _schema_subcol(schema_family, sub_index)
    if schema_slug:
        return schema_slug

    # 2. Legacy I-group keyed table (V7-specific layouts: RDA, sleep stages,
    #    spike-density rate variants, seizure event sub-cols, etc.)
    #
    #    Keyed on ABSOLUTE I-numbers, which move whenever the panel is edited, so
    #    it is consulted only when the MMX could not resolve the instrument. With
    #    a resolved instrument the trend-name parsing below is authoritative.
    #    Applying it regardless fired on 36 I-groups of the V8 export and returned
    #    V7 labels: "Boolean LPD+" and "Boolean LRD+" both became 'max', collapsing
    #    two distinct periodic-discharge channels onto pd_max.
    if mmx_name is None and i_group in I_GROUP_SUBCOLUMN_NAMES:
        names = I_GROUP_SUBCOLUMN_NAMES[i_group]
        idx = sub_index - 1  # convert 1-indexed to 0-indexed
        if 0 <= idx < len(names):
            return names[idx]

    # Asymmetry index: extract band + region from trend
    # NOTE: check REASI before EASI — "EASI" is a substring of "REASI"
    if family == "asymmetry" and ("EASI" in trend_name or "REASI" in trend_name):
        parts = []
        index_type = "reasi" if "REASI" in trend_name else "easi"
        for hz_str, band in ASYMMETRY_BANDS.items():
            if hz_str in trend_name:
                parts.append(band)
                break
        for region_str, region_label in ASYMMETRY_REGIONS.items():
            if region_str in trend_name:
                parts.append(region_label)
                break
        if parts:
            return f"{index_type}_{'_'.join(parts)}"

    # Sleep: I123-I130 all handled by lookup; others fall through here
    if family == "sleep":
        return "stage_display"

    # Spike density: use the laterality from the trend name
    if family == "spike_density" and trend_name:
        t = trend_name.lower()
        rate = "per_sec" if "per sec" in t else "per_10s" if "per 10" in t else ""
        # SpikeGen = generalized regardless of electrode content
        if "spikegen" in t or "spike gen" in t:
            return f"generalized_{rate}" if rate else "generalized"
        # Prioritize unambiguous composite keywords
        for kw in ("burst bilateral", "all foci", "generalized", "vertex", "threshold"):
            if kw in t:
                label = kw.replace(" ", "_")
                return f"{label}_{rate}" if rate else label
        # EventDensity Spike electrode chain laterality (new MMX-Name format):
        # "EventDensity Spike Fp1 OR Spike F3 OR ..." → left; "...Fp2 OR..." → right
        if "spike" in t:
            _left = {"fp1", "f3", "c3", "p3", "o1", "f7", "t3", "t5", "t7", "p7", "a1"}
            _right = {"fp2", "f4", "c4", "p4", "o2", "f8", "t4", "t6", "t8", "p8", "a2"}
            lc = sum(1 for e in _left if re.search(r"\b" + e + r"\b", t))
            rc = sum(1 for e in _right if re.search(r"\b" + e + r"\b", t))
            if lc > rc:
                return f"left_{rate}" if rate else "left"
            if rc > lc:
                return f"right_{rate}" if rate else "right"
        # Keyword fallback for old-style "left / right" trend names
        for kw in ("left", "right", "burst"):
            if kw in t:
                return f"{kw}_{rate}" if rate else kw

    # FFT power: derive from band + region
    if family in ("fft_power", "fft_power_ratio", "alpha_variability"):
        hemi = extract_hemisphere(trend_name)
        reg = extract_region(trend_name)
        elec = extract_electrode(trend_name)
        if elec:
            return elec.lower()
        if hemi and reg:
            return f"{hemi}_{reg}"

    # RDA: from lookup table; fallback to laterality keyword scan
    if family == "rda":
        for kw in ("blue", "left"):
            if kw in trend_name.lower():
                return "left"
        for kw in ("red", "right"):
            if kw in trend_name.lower():
                return "right"
        for kw in ("green", "gen"):
            if kw in trend_name.lower():
                return "generalized"

    # Rhythmic delta booleans: name the brain region, not the Persyst acronym
    # (Craig, 2026-08-22). LAD/LPD are the left anterior and left posterior
    # quadrant flags; LRD is the left HEMISPHERE flag — a boolean OR of the two,
    # which the MMX confirms by combining both quadrant expressions. R* mirror
    # it on the right. "lad" told the reader nothing and invited the ACNS
    # periodic-discharge reading; the region does not.
    if family == "rhythmic_delta":
        m = re.search(r"Boolean\s+([LR])([APR])D\+?", trend_name, re.IGNORECASE)
        if m:
            side = {"l": "left", "r": "right"}[m.group(1).lower()]
            part = {"a": "anterior", "p": "posterior", "r": "hemisphere"}[m.group(2).lower()]
            return f"{side}_{part}"

    # aEEG: left/right from trend name
    if family == "aeeg":
        hemi = extract_hemisphere(trend_name)
        if hemi:
            return hemi

    return ""


def generate_common_name(entry: "ColumnEntry") -> str:  # type: ignore[name-defined]
    """Build a machine-readable, R/Python-valid identifier for this column.

    Format varies by family:
    - fft_power:          ``fft_{band}_{hemisphere}_{region}`` (+ ``_asym`` for Asym regions)
    - adr (band/1-4):     ``adr_{location}`` (8-13/1-4) or ``tdr_{location}`` (4-8/1-4)
    - relative_power:     ``rel_{band}_{location}`` (band / total 1-30 Hz, V8+)
    - alpha_variability:  ``rav_{hemisphere}_{region}`` or ``rav_{electrode_chain}``
    - fft_power_ratio:    ``ratio_{location}`` (unrecognized ratio denominator)
    - artifact_intensity: ``artifact_intensity_{component}``
    - electrode_quality:  ``electrode_quality_{electrode}``
    - rda:                ``rda_{laterality}``
    - periodic_discharge: ``rhythmic_delta_{acronym}``
    - seizure_*:          ``seizure_prob_p14`` / ``seizure_detection`` / ``seizure_notification``
    - spike_density:      ``spike_{sub_column_name}``
    - sleep:              ``sleep_{sub_column_name}``
    - aeeg:               ``aeeg_{hemisphere|region}_{sub_column_name}``
    - asymmetry:          ``asymmetry_{sub_column_name}`` (already encoded)
    - spectral_edge:      ``sef{number}``
    - suppression_ratio:  ``suppression_{hemisphere}[_{region}]``
    - heart_rate:         ``heart_rate``
    - coherence_*:        ``coherence_{electrode_pair}``
    - rhythmicity:        ``rhythmicity_{sub}``

    ``{location}`` = electrode chain, ``all`` (All 10-20), or ``{hemi}_{region}``.
    """
    fam = entry.family
    sub = entry.sub_column_name
    band = entry.frequency_band
    hemi = entry.hemisphere
    reg = entry.region
    elec = entry.electrode

    def _slug(*parts: str) -> str:
        """Join non-empty parts with underscores, lowercased and identifier-safe.

        Every exported column name passes through here, so this is the single
        place that guarantees the result is usable as an identifier downstream:
        R's ``data.frame`` mangles anything outside ``[A-Za-z0-9_.]``, SQL needs
        quoting for the rest, and a ``/`` breaks file-per-column exports
        outright. Observed offenders before this guard were the rhythmicity
        threshold columns -- ``..._gte_1.1hz`` and ``..._gte_5uv/hz``.

        Anything outside ``[a-z0-9_]`` becomes ``_``; runs collapse; edges are
        trimmed. Digits and the ``_`` separator are preserved, so deliberate
        forms like ``9_00hz`` (see ``_spectrogram_freq_label``) survive intact.
        """
        joined = "_".join(p.lower().replace(" ", "_") for p in parts if p)
        safe = re.sub(r"[^a-z0-9_]", "_", joined)
        return re.sub(r"_+", "_", safe).strip("_")

    # --- Detect running-average variant from trend name ---
    # Handles old human-readable ("2 min. running ave.") and new MMX-Name bracket form
    # ("Time Avg <0,120> [...]" = 0–120 s = 2 min; "<0,64>" = 64 s)
    trend = entry.trend_name
    # Averaging window is IDENTITY, so read it from the MMX. Persyst leaves the
    # display label saying "64 sec running ave." when the window has been changed
    # -- V8 shipped two Right Anterior FFT_Power instruments at <0,1800> whose 14
    # siblings are <0,64>, and reading the label named them _avg64s. Falls back to
    # the label when no instrument resolved.
    _win = re.search(r"\bTime\s+Avg\s*<\s*\d+\s*,\s*(\d+)\s*>", entry.mmx_name or "")
    if _win:
        _secs = int(_win.group(1))
        _is_avg2m = _secs == 120
        _is_avg64s = _secs == 64
        _is_avg_other = _secs not in (64, 120)
    else:
        _is_avg2m = ("2 min" in trend and "running" in trend.lower()) or "<0,120>" in trend
        _is_avg64s = ("64 sec" in trend and "running" in trend.lower()) or "<0,64>" in trend
        _secs = 0
        _is_avg_other = False

    # --- FFT power (absolute) ---
    # "Time (2 min. running ave.)" → prefix fft_avg2m_
    # "Time (64 sec running ave)" → prefix fft_avg64s_
    # Raw (no Time prefix) → prefix fft_
    # Whole-brain ("All 10-20") and asymmetry detection, shared by the power /
    # ratio families below. The trend tail is authoritative for the channel set.
    _tail_lower = _trend_tail(entry.trend_name).lower()
    _is_all = "all 10-20" in _tail_lower or _tail_lower.strip() == "all"
    _is_asym = "asym" in entry.trend_name.lower()

    def _ratio_location() -> str:
        """Channel-set slug for a ratio/power trend: electrode chain, 'all', or hemi+region."""
        if elec:
            return elec.lower()
        if _is_all:
            return "all"
        return _slug(hemi, reg)

    if fam == "fft_power":
        if _is_avg2m:
            prefix = "fft_avg2m"
        elif _is_avg64s:
            prefix = "fft_avg64s"
        elif _is_avg_other:
            # A window Persyst does not use elsewhere. Name it rather than
            # dropping the token, which would make a 30-minute average
            # indistinguishable from the unaveraged channel.
            prefix = f"fft_avg{_secs}s"
        else:
            prefix = "fft"
        # I10/I12 are identical 2-min averages (display duplicate); disambiguate
        # Without a location token the All 10-20 columns come out as bare
        # "fft_delta", which reads as a family name rather than a column and
        # collides conceptually with the derived fft_{band}_{region} features.
        # The ratio families already route through _ratio_location() for this.
        _loc = elec.lower() if elec else ("all" if _is_all else _slug(hemi, reg))
        name = _slug(prefix, band or "power", _loc)
        # Asymmetry-region power (Persyst "Asym Anterior/Posterior") gets an _asym
        # suffix so it stays distinct from the non-lateralized Anterior/Posterior
        # channel power (V8+) and from any downstream bilateral aggregate.
        if _is_asym:
            name = f"{name}_asym"
        # The I10/I12 display duplicate used to be disambiguated with
        # f"_d{i_group}", which bakes an absolute I-number into the exported
        # identifier -- the exact volatility this work removed everywhere else.
        # ensure_unique_common_names handles it, stably and visibly.
        return name

    # --- Relative band power: band / total 1-30 Hz broadband (V8+) ---
    # Persyst "FFT PowerRatio, {band}/1-30 Hz, {region}". Distinct from the
    # pipeline-computed rel_{band}_{region} (denominator = δ+θ+α+β band-sum);
    # the compute step yields to this Persyst-native value when present.
    if fam == "relative_power":
        _, band_desc = classify_ratio(entry.trend_name)
        location = _ratio_location()
        prefix = _slug("rel", band_desc) if band_desc and band_desc != "broadband" else "rel"
        if _is_asym:
            prefix = f"{prefix}_asym" if not location else prefix
        name = _slug(prefix, location) if location else prefix
        return f"{name}_asym" if (_is_asym and location) else name

    # --- ADR / TDR: band-vs-delta ratio (numerator / 1-4 Hz) ---
    # 8-13/1-4 = ADR (alpha/delta), 4-8/1-4 = TDR (theta/delta). classify_ratio
    # returns the kind so the two no longer collide onto a shared "adr" slug.
    if fam == "adr":
        _, kind = classify_ratio(entry.trend_name)
        base = kind if kind in ("adr", "tdr") else "adr"
        if _is_avg2m:
            base = f"{base}_avg"
        elif _is_avg64s:
            base = f"{base}_avg64s"
        location = _ratio_location()
        name = _slug(base, location) if location else base
        return f"{name}_asym" if (_is_asym and location) else name

    # --- RAV / Relative Alpha variability (6-14/1-20 Hz) ---
    if fam == "alpha_variability":
        location = _ratio_location()
        # RAV = Relative Alpha VARIABILITY, and Persyst pins it to one ratio: the
        # panels named "Relative Alpha Variability (RAV)" and "... (Quadrant)"
        # contain only FFT_PowerRatio 6-14//1-20. Anything reaching this family
        # is that measure -- alpha-over-broadband (8-13//1-30) is relative POWER
        # and is classified into relative_power by classify_ratio.
        if _is_avg2m:
            prefix = "rav_avg"
        elif _is_avg64s:
            prefix = "rav_avg64s"
        elif _is_avg_other:
            prefix = f"rav_avg{_secs}s"
        else:
            prefix = "rav"
        name = _slug(prefix, location) if location else prefix
        return f"{name}_asym" if (_is_asym and location) else name

    # --- Other / unrecognized power ratios ---
    if fam == "fft_power_ratio":
        location = _ratio_location()
        return _slug("ratio", location) if location else "ratio"

    # --- Artifact / quality ---
    if fam == "artifact_intensity":
        return _slug("artifact_intensity", sub)
    if fam == "electrode_quality":
        # POSITIONAL ONLY — never name the electrode (Craig, 2026-08-21).
        # ESQ sub-columns map 1:1 to the recording's acquisition channels, whose
        # order and count come from that recording's own .lay [ChannelMap] and
        # vary between recordings (4290-1 ends Fpz, Pz; 4290-4 ends Pz, Ref).
        # The previous hardcoded list was wrong in 21 of 22 positions and turned
        # a real disconnect pattern into a fabricated one. Emit the ordinal and
        # let electrode identity travel as per-recording metadata instead.
        return f"esq_ch{entry.sub_index:02d}"

    # --- Status Epilepticus (Persyst-native ESE metric, V8+) ---
    # Distinct slug namespace (``status_epilepticus_persyst_*``) so it never
    # overwrites the pipeline-calculated ``status_epilepticus_screen_flag`` /
    # ``has_status_epilepticus``. Persyst emits 6 variants — 3 methods
    # (ACNS / Advanced / Combined) × 2 outputs (Binary / Percent).
    if fam == "status_epilepticus":
        t = entry.trend_name.lower()
        method = ("acns" if "acns" in t else
                  "advanced" if "advanced" in t else
                  "combined" if "combined" in t else "")
        output = ("percent" if "percent" in t else
                  "binary" if "binary" in t else "")
        parts = [p for p in ("status_epilepticus_persyst", method, output) if p]
        if not method and not output:
            m = re.search(r"(\d+)\s*$", entry.trend_name)
            if m:
                parts.append(m.group(1))
        return _slug(*parts)

    # --- Seizure Burden (Persyst-native, V8+) ---
    # Distinct from the calculated ``seizure_burden_pct`` / ``seizure_burden_hours``.
    # Persyst emits 2 variants — Percentage and Category (5-min assessment window).
    if fam == "seizure_burden":
        t = entry.trend_name.lower()
        output = ("category" if "category" in t else
                  "percentage" if ("percentage" in t or "percent" in t) else "")
        parts = [p for p in ("seizure_burden_persyst", output) if p]
        if not output:
            m = re.search(r"(\d+)\s*$", entry.trend_name)
            if m:
                parts.append(m.group(1))
        return _slug(*parts)

    # --- RDA ---
    if fam == "rda":
        return _slug("rda", sub)

    # --- Peak envelope ---
    if fam == "peak_envelope":
        return _slug("peak_envelope", hemi, reg)

    # --- Seizure ---
    # From MMX (PedQuEST_Pennsieve_V7_research.mmx; unchanged from V3), SeizureProbabilityP14 engine:
    #   I120 = notifications (OutputIndex 2, SumType=2)
    #   I121 = continuous probability value (OutputIndex 0, SumType=9)
    #   I122 = binary detection events (OutputIndex 1, SumType=8)
    # I119 has 2 sub-columns: _1=detection event, _2=notification event
    # With MMX-first family resolution, seizure_probability and seizure_detection are
    # assigned from Instrument Name prefix ("SeizureProbabilityP14 Probability" vs
    # "SeizureProbabilityP14 Detections") — no I-group gating required.
    if fam == "seizure_probability":
        # I144 and I145 share a display label and differ only in the MMX
        # instrument suffix (Probability vs Detections); without the
        # sub-column they collide.
        return _slug("seizure_probability_p14", sub)
    if fam == "seizure_detection":
        # Three distinct instruments reach this family and the sub-column alone
        # cannot separate them, so all three collapsed onto
        # seizure_detection_event / __dup2 / __dup3:
        #   SeizureEventsP14                     the display overlay pair
        #                                        (sub 1 detection, sub 2 notification)
        #   SeizureProbabilityP14 Detections     the detections channel itself
        #   Time Max <0,120> [ ...Detections]    a 2-minute running MAX of it
        # A running Max over an instrument is a different column from the
        # instrument and must never share its identifier -- the same rule the
        # seizure_probability branch applies above.
        _mmx = entry.mmx_name or ""
        if "SeizureProbabilityP14" in _mmx:
            _win = re.search(r"\bTime\s+(Max|Avg|Min)\s*<\s*\d+\s*,\s*(\d+)\s*>", _mmx)
            if _win:
                return f"seizure_detection_p14_{_win.group(1).lower()}{_win.group(2)}s"
            return "seizure_detection_p14"
        return _slug("seizure", sub or "detection")
    if fam == "seizure_notification":
        return "seizure_notification_p14"

    # --- Spike density ---
    if fam == "spike_density":
        name = _slug("spike", sub) if sub else "spike"
        # Rate cadence: "count per sec" and "count per 10s" of the same detector
        # are separate columns under labels differing only in that phrase.
        _t = entry.trend_name.lower()
        if not name.endswith(("per_sec", "per_10s")):
            if "per sec" in _t:
                name = f"{name}_per_sec"
            elif "per 10s" in _t or "per ten sec" in _t or "per 10 sec" in _t:
                name = f"{name}_per_10s"
        return name

    # --- Sleep ---
    if fam == "sleep":
        return _slug("sleep", sub) if sub else "sleep_stage"

    # --- aEEG ---
    # Location is the hemisphere when present (Left/Right), else the region
    # (Anterior/Posterior channel sets, V8+). Without this, the non-lateralized
    # aEEG Anterior/Posterior trends both collapse onto a bare aeeg_{sub} slug.
    if fam == "aeeg":
        location = hemi or reg
        return _slug("aeeg", location, sub)

    # --- Asymmetry (index columns have encoded sub_column_name) ---
    if fam == "asymmetry":
        if sub:
            return _slug("asymmetry", sub)
        # Spectrogram sub-column: encode channel group + frequency range
        # Channel groups: electrode chains (F3C3P3) or Asym regions (Asym Hemi, Asym Temporal, etc.)
        elec_part = elec.lower() if elec else _slug(hemi, reg)
        if not elec_part:
            # Extract "Asym X" channel group from trend name
            m = re.search(r"Asym\s+(\w+)", trend)
            if m:
                elec_part = m.group(1).lower()  # "hemi", "parasagittal", "temporal"
        freq_label = _spectrogram_freq_label("asymmetry", entry.sub_index)
        return _slug("asymmetry_spec", elec_part, freq_label)

    # --- Spectral edge ---
    # MMX emits one FFT_Edge instrument per (percentile, channels) pair.
    # Channels include "All 10-20" (whole brain), regional pairs
    # ("Left Anterior", "Right Posterior", etc.), and asymmetry groupings
    # ("Asym Anterior", "Asym Posterior"). The older slug dropped the channels
    # token entirely, so every SEF95 variant collided onto `sef_95`. Include
    # the channels slug so each regional variant gets its own column.
    if fam == "spectral_edge":
        m = re.search(r"SEF\s*(\d+)", entry.trend_name)
        if not m:
            m = re.search(r"FFT_Edge\s+(\d+)", entry.trend_name)
        sef_num = m.group(1) if m else ""
        tail = _trend_tail(entry.trend_name).lower()
        # Map "All 10-20" → "all" (user convention); keep other tails verbatim.
        if "all 10-20" in tail or tail == "all":
            channels_slug = "all"
        elif tail.startswith("asym "):
            channels_slug = _slug("asym", tail.removeprefix("asym ").strip())
        elif hemi and reg:
            channels_slug = _slug(hemi, reg)
        elif tail:
            channels_slug = _slug(tail)
        else:
            channels_slug = "all"
        return _slug("sef", sef_num, channels_slug)

    # --- Suppression ratio ---
    # V7 MMX Amplitude01 emits per-region BSR: Left/Right × Anterior/Hemisphere/Posterior
    # plus the All-10-20 whole-brain variant. Each is a distinct physical signal, so
    # the slug must encode both hemisphere AND region. The bare `suppression_{hemi}`
    # slug is reserved for region=Hemisphere (the dashboard's "Suppression — Left/Right"
    # label implies whole-hemisphere); Anterior/Posterior get explicit region suffixes.
    if fam == "suppression_ratio":
        tail_lower = _trend_tail(entry.trend_name).lower()
        if "all" in tail_lower or "all 10-20" in tail_lower:
            return "suppression_all"
        if reg and reg.lower() != "hemisphere":
            return _slug("suppression", hemi, reg)
        return _slug("suppression", hemi)

    # --- Heart rate ---
    # MMX has two HR instruments on different channels (EKG, X2); disambiguate
    if fam == "heart_rate":
        # Was: return "heart_rate" when i_group == 72 else heart_rate_{i_group}.
        # The full Research panel puts HR at I69, so the same instrument was
        # heart_rate in one panel and heart_rate_69 in another -- a guaranteed
        # join break between two exports of the same recording.
        #
        # The channel distinguishes genuine multiple HR sources where it is
        # populated. Where it is not, the template still ships two instruments
        # ("Heart Rate" and its "Heart Rate01" alias) that export as two columns
        # under the CSV headers "Heart Rate 1" and "Heart Rate 2". Take the
        # ordinal from that header rather than letting the second fall to the
        # uniqueness backstop as heart_rate__dup2, which names nothing. Whether
        # the two carry distinct signals is unconfirmed -- tier EMP.
        if entry.electrode:
            return _slug("heart_rate", entry.electrode.lower())
        _ord = re.search(r"\bHeart\s*Rate\s*(\d+)\s*$", entry.trend_name or "")
        if _ord and _ord.group(1) != "1":
            return f"heart_rate_{_ord.group(1)}"
        return "heart_rate"

    # --- Rhythmic delta booleans (Boolean LAD+/LPD+/LRD+/RAD+/RPD+/RRD+) ---
    # NOT periodic discharges. The MMX defines each as a threshold on the
    # Rhythmicity Spectrogram DELTA band — peak frequency >= 1.1 Hz AND rhythmic
    # power >= 5 uV/Hz — over one quadrant. The old family name
    # "periodic_discharge" and the `pd_` prefix read as ACNS lateralized
    # periodic discharges, a different and more alarming pattern.
    # Acronyms are kept verbatim so each column traces to its Persyst label:
    # L/R = side, A/P = anterior/posterior, R = the side's combined rhythmic
    # flag, D = delta.
    if fam == "rhythmic_delta":
        return _slug("rhythmic_delta", sub) if sub else "rhythmic_delta"

    # --- Rhythmicity (spectrogram / SumValues / Thresholds) ---
    if fam == "rhythmicity":
        trend = entry.trend_name
        elec_part = elec.lower() if elec else _slug(hemi, reg)

        # SumValues: scalar delta freq or delta power extracted from spectrogram
        # Trend: "SumValues LA delta freq, ..." or "SumValues LP delta power, ..."
        if trend.startswith("SumValues"):
            measure = "delta_freq" if "delta freq" in trend else "delta_power" if "delta power" in trend else "sum"
            return _slug("rhythmicity_sum", elec_part, measure)

        # Threshold booleans: periodic discharge indicators
        # Trend: "Threshold LAD>=1.1Hz, ..." or "Threshold LPD>=5uV/Hz, ..."
        if trend.startswith("Threshold"):
            # Extract the threshold label (e.g., "LAD>=1.1Hz" or "LPD>=5uV/Hz")
            m = re.match(r"Threshold\s+(\S+),", trend)
            thresh_label = m.group(1).lower().replace(">=", "_gte_") if m else str(entry.i_group)
            return _slug("rhythmicity_thresh", elec_part, thresh_label)

        # FreqPow regional summaries: 16 sub-columns, NOT spectrogram bins.
        #
        # These were being labelled with the 97-bin sqrt formula, so all 16 came
        # out as sub-2.7 Hz frequencies and every column read as delta. The
        # layout is 4 frequency bands x 4 values per band
        # (PersystTrendCSV_Format_Reference.md §3.27, and §3.0's sub-column
        # contract). Band edges are taken from Persyst's Rhythmicity help page,
        # which the data supports: observed maxima of the position-1 columns are
        # 3.96 / 8.59 / 13.89 / 22.90 Hz. §3.27's "delta/theta/alpha/beta" gloss
        # is explicitly approximate and its 4-8 / 8-13 upper edges are below
        # those maxima, so the Hz ranges are used rather than clinical band names
        # that the values would contradict.
        #
        # Positions 1 and 3 within each block are confirmed against the §3.25
        # SumValues scalars. Positions 2 and 4 are documented as NOT confirmed,
        # so they are labelled positionally rather than guessed — a wrong
        # semantic label here is the same class of error as rda_rem.
        if "FreqPow" in trend:
            band_idx, pos = divmod(entry.sub_index - 1, 4)
            # The 4x4 layout is only documented for 16 sub-columns. Outside
            # that range the band edges are an assumption, so label
            # positionally rather than assert a frequency.
            if 0 <= band_idx < len(_RHYTHMICITY_FREQPOW_BANDS) and entry.sub_index <= 16:
                band = _RHYTHMICITY_FREQPOW_BANDS[band_idx]
                value = _RHYTHMICITY_FREQPOW_POSITIONS[pos]
                return _slug("rhythmicity_freqpow", elec_part, band, value)
            return _slug("rhythmicity_freqpow", elec_part, f"sub{entry.sub_index}")

        # Full spectrogram (97 bins per derivation)
        freq_label = _spectrogram_freq_label("rhythmicity", entry.sub_index)
        return _slug("rhythmicity", elec_part, freq_label)

    # --- FFT spectrogram ---
    if fam == "fft_spectrogram":
        elec_part = elec.lower() if elec else _slug(hemi, reg)
        freq_label = _spectrogram_freq_label("fft_spectrogram", entry.sub_index)
        return _slug("fft_spec", elec_part, freq_label)

    # --- Coherence spectrogram ---
    if fam == "coherence_spectrogram":
        elec_part = elec.lower() if elec else "ch"
        # Coherence_Avg and Coherence_Spectrogram are different instruments over
        # the same electrode pair. The average is a SINGLE value across the whole
        # 0-32 Hz range, so labelling it with a bin-centre frequency asserts
        # something false -- it was coming out as `coherence_c3p3_0.00hz`, a DC
        # bin label on a broadband average, and colliding with the spectrogram's
        # real first bin. Name it by its range instead.
        if "coherence_avg" in entry.trend_name.lower().replace(" ", "_"):
            lo, hi = entry.freq_min_hz, entry.freq_max_hz
            # Same identifier-safety rule as _spectrogram_freq_label: no "." in
            # a slug. Fractional bounds do occur in this schema (0.75, 1.125, …),
            # so ":g" alone would emit "0.5_0.75hz".
            span = (f"{lo:g}_{hi:g}hz".replace(".", "_")
                    if lo is not None and hi is not None else "broadband")
            return _slug("coherence_avg", elec_part, span)
        freq_label = _spectrogram_freq_label("coherence_spectrogram", entry.sub_index)
        return _slug("coherence_spec", elec_part, freq_label)

    # --- Fallbacks ---
    if fam == "annotation":
        return "annotation"
    if fam == "time_display":
        return "time_display"

    # Generic fallback: family + I-code
    code_slug = entry.code.replace("_", "s")
    return _slug(fam, code_slug)


def ensure_unique_common_names(entries: list[ColumnEntry]) -> list[str]:
    """Force ``common_name`` to be unique within an export. Returns what changed.

    ``common_name`` is the column name in exported datasets, so a duplicate is a
    silent overwrite (or a mangled suffix) in any dataframe built from it, and
    the affected columns become unrecoverable downstream. Most duplicates are
    resolved upstream by disambiguating from the MMX, but Persyst genuinely does
    ship identical instruments -- the Research panel carries two
    "Asymmetry, Relative Index (REASI) 4-8 Asym Hemi" entries with the same name
    and the same definition, separable only by position.

    For those, the second and later occurrences (in panel order) get a ``_2``,
    ``_3`` ... suffix. The first keeps its name, so existing identifiers are
    preserved. An occurrence index among identical siblings is used rather than
    the I-code: absolute I-numbers shift whenever the panel is edited, whereas
    this is stable as long as the duplicate set is.
    """
    # Every name that has been handed out, including generated suffixes. Tracking
    # only the base names is not enough: a generated "foo_2" can collide with a
    # naturally-occurring "foo_2", which would defeat the guarantee this function
    # exists to make.
    # Reserve every naturally-occurring name FIRST. Assigning suffixes in a
    # single pass let a synthesised "foo_2" claim a name Persyst had already
    # given to a different instrument, pushing the real one to "foo_2_2" -- an
    # identity swap, silent and type-correct, which is worse for a downstream
    # join than the collision it was fixing. sleep_stage_0..5 are exactly this
    # shape.
    seen: set[str] = set()
    reserved: set[str] = set()
    for e in entries:
        if e.common_name:
            reserved.add(e.common_name)

    taken = set(reserved)
    renamed: list[str] = []
    for e in entries:
        if not e.common_name:
            continue
        if e.common_name not in seen:
            seen.add(e.common_name)
            continue
        original = e.common_name
        # "__dup" cannot collide with a Persyst-derived name: nothing in the
        # naming scheme emits a double underscore.
        n = 2
        candidate = f"{original}__dup{n}"
        while candidate in taken:
            n += 1
            candidate = f"{original}__dup{n}"
        e.common_name = candidate
        taken.add(candidate)
        renamed.append(f"{e.code}: {original} -> {candidate}")
    if renamed:
        logger.warning(
            "column identity: %d duplicate common_name(s) suffixed; Persyst ships "
            "identical instruments that only position separates: %s",
            len(renamed), "; ".join(renamed[:5]) + (" ..." if len(renamed) > 5 else ""),
        )
    return renamed


# ---------------------------------------------------------------------------
# Schema builders
# ---------------------------------------------------------------------------

def build_column_schema(code_to_description: dict[str, str]) -> list[ColumnEntry]:
    """Build a typed column schema from a ``ParsedExport.code_to_description`` dict.

    Each key is an I-code like ``"I34_1"`` and each value is the human-readable
    trend description.  Returns a list of :class:`ColumnEntry` sorted by
    ``col_index``.
    """
    code_re = re.compile(r"^I(\d+)_(\d+)$")
    entries: list[ColumnEntry] = []

    for idx, (code, raw_trend_name) in enumerate(code_to_description.items()):
        m = code_re.match(code)
        if not m:
            continue

        i_group = int(m.group(1))
        sub_index = int(m.group(2))

        # Normalize old 10-20 electrode names (T3→T7, T4→T8, T5→P7, T6→P8)
        trend_name = normalize_electrode_names(raw_trend_name)

        family = classify_family(trend_name)
        freq_min, freq_max = extract_frequency_range(trend_name)

        # Spectrogram columns don't have Hz in their trend name — derive from schema.
        # Schema encodes the correct formula per family (sqrt for rhythmicity,
        # linear for FFT/asym/coherence). Returns the bin's center frequency in Hz.
        if freq_min is None and freq_max is None:
            spec_key = _SPEC_FAMILY_MAP.get(family)
            if spec_key:
                from qeeg.ingestion.subcol_schema import get_spectrogram_bin_freq
                center = get_spectrogram_bin_freq(spec_key, sub_index)
                if center is not None:
                    # Half-bin window around the center for band-classification.
                    # Use the legacy linear approximation as the half-bin width.
                    half = SPECTROGRAM_FREQ_MAP[spec_key]["resolution_hz"] / 2.0
                    freq_min = max(0.0, center - half)
                    freq_max = center + half

        band = ""
        if freq_min is not None and freq_max is not None:
            band = map_to_band(freq_min, freq_max)

        # Hemisphere/region: for electrode chains look up the chain mapping
        elec = extract_electrode(trend_name)
        if elec in ELECTRODE_CHAIN_REGIONS:
            hemi, _reg = ELECTRODE_CHAIN_REGIONS[elec]
            reg = ""  # chain doesn't map to a single region label
        else:
            hemi = extract_hemisphere(trend_name)
            reg = extract_region(trend_name)

        entry = ColumnEntry(
            col_index=idx,
            code=code,
            i_group=i_group,
            sub_index=sub_index,
            trend_name=trend_name,
            family=family,
            frequency_band=band,
            freq_min_hz=freq_min,
            freq_max_hz=freq_max,
            hemisphere=hemi,
            region=reg,
            electrode=elec,
        )

        entry.sub_column_name = get_subcolumn_name(i_group, sub_index, trend_name, family)
        entry.common_name = generate_common_name(entry)

        entries.append(entry)

    entries.sort(key=lambda e: e.col_index)
    ensure_unique_common_names(entries)
    return entries


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

# Persyst appends these two pseudo-columns after the panel's instruments. They
# have no MMX Instrument, so failing to resolve them is expected, not an error.
TAIL_PSEUDO_COLUMNS = 2


def resolve_export_panel(mmx: "MMXConfig", max_i_group: int):
    """Identify which MMX panel an export came from, using the ordinal invariant.

    Persyst serialises the panel in display order and appends ``Comment`` and
    ``Time``, so ``len(panel.instruments) + 2 == max(i_group)``. Verified with
    zero violations across all four real 4290-1 exports (Research-Trends 230+2
    -> I232; Research 367+2 -> I369).

    Returns the unique matching :class:`PanelDef`, or ``None`` if no panel or
    more than one panel fits (in which case the caller must not trust ordinals).
    """
    hits = [p for p in mmx.panels.values()
            if len(p.instruments) + TAIL_PSEUDO_COLUMNS == max_i_group]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        logger.warning(
            "MMX: %d panels match max I%d (%s) — ordinal resolution disabled",
            len(hits), max_i_group, ", ".join(p.name for p in hits),
        )
    else:
        logger.warning("MMX: no panel has %d instruments + %d tail columns — "
                       "ordinal resolution disabled",
                       max_i_group - TAIL_PSEUDO_COLUMNS, TAIL_PSEUDO_COLUMNS)
    return None


def build_column_schema_with_mmx(
    code_to_description: dict[str, str],
    mmx: "MMXConfig",
) -> list[ColumnEntry]:
    """Like :func:`build_column_schema` but resolves family/region from the MMX.

    Resolution is **ordinal-primary**: ``i_group`` is the 1-based position of the
    instrument within the export panel, so ``panel.instruments[i_group - 1]`` is
    the authoritative identity. Exact-matching the CSV trend name against
    ``mmx.instruments`` — the previous strategy — resolves only 0.3% of columns,
    because MMX Instrument names are internal expressions (``"= 0 <0>
    [SleepStages]"``) while the CSV carries display labels (``"aEEG, All 10-20"``).

    Ordinal is also the *only* discriminator for instruments Persyst exports under
    an identical display label — the six ``SleepStages`` columns, seizure
    probability vs detections, and spike laterality. Name-based resolution cannot
    separate those at all.

    Falls back to name lookup, then to regex classification, when the panel cannot
    be identified.
    """
    from qeeg.ingestion.mmx_parser import MMXConfig  # local import avoids circular dep

    code_re = re.compile(r"^I(\d+)_(\d+)$")
    entries: list[ColumnEntry] = []

    # Identify the export panel once, from the highest I-group present.
    _groups = [int(m.group(1)) for m in
               (code_re.match(c) for c in code_to_description) if m]
    panel = resolve_export_panel(mmx, max(_groups)) if _groups else None

    for idx, (code, raw_trend_name) in enumerate(code_to_description.items()):
        m = code_re.match(code)
        if not m:
            continue

        i_group = int(m.group(1))
        sub_index = int(m.group(2))

        trend_name = normalize_electrode_names(raw_trend_name)

        # --- MMX resolution: ordinal first, then name ---
        mmx_inst = None
        resolution = ""
        if panel is not None and 1 <= i_group <= len(panel.instruments):
            mmx_inst = panel.instruments[i_group - 1]
            resolution = "ordinal"
        if mmx_inst is None:
            mmx_inst = mmx.instruments.get(trend_name)
            if mmx_inst is not None:
                resolution = "name"
            elif panel is not None and i_group > len(panel.instruments):
                resolution = "tail"
            else:
                resolution = "regex"

        if mmx_inst is not None:
            # Family comes from the DISPLAY LABEL, not the MMX instrument name.
            # For derived Boolean detectors the MMX Name is the underlying formula
            # -- "[>= 1.1 <0> [SumValues_Abs_0-0 [Rhythmicity Spectrogram 3.00 Left
            # Anterior_avg]]]" -- so _infer_family reports the substrate
            # (rhythmicity) rather than what the instrument measures. The CSV label
            # ("Boolean LPD+", "RDA N3") carries the real semantics. Taking the MMX
            # family here regressed 72 columns: pd_lad -> rhythmicity_*,
            # artifact_detector_fp1 -> other_i6s1.
            #
            # The MMX is authoritative for *identity* (which instrument this is, via
            # ordinal) and for Channels; the label is authoritative for *meaning*.
            family = classify_family(trend_name)
            if family in ("", "other"):
                family = canonical_family(mmx_inst.family)
            channels = mmx_inst.channels  # authoritative: "Left Anterior", "All 10-20", …
            hemi = "left" if "Left" in channels else ("right" if "Right" in channels else "")
            reg = (
                "anterior"   if "Anterior"   in channels else
                "posterior"  if "Posterior"  in channels else
                "hemisphere" if "Hemisphere" in channels else
                ""
            )
            # Fall through to trend-name extraction if Channels is empty
            if not hemi:
                hemi = extract_hemisphere(trend_name)
            if not reg:
                reg = extract_region(trend_name)
        else:
            # Past the end of the panel is the expected Comment/Time tail, not a
            # failure. Anything else genuinely did not resolve.
            if panel is None or i_group <= len(panel.instruments):
                logger.warning("MMX: unmatched trend name: %r", trend_name)
            family = classify_family(trend_name)
            hemi = extract_hemisphere(trend_name)
            reg = extract_region(trend_name)

        freq_min, freq_max = extract_frequency_range(trend_name)

        # Spectrogram bin freq from schema (see qeeg.ingestion.subcol_schema).
        if freq_min is None and freq_max is None:
            spec_key = _SPEC_FAMILY_MAP.get(family)
            if spec_key:
                from qeeg.ingestion.subcol_schema import get_spectrogram_bin_freq
                center = get_spectrogram_bin_freq(spec_key, sub_index)
                if center is not None:
                    half = SPECTROGRAM_FREQ_MAP[spec_key]["resolution_hz"] / 2.0
                    freq_min = max(0.0, center - half)
                    freq_max = center + half

        band = ""
        if freq_min is not None and freq_max is not None:
            band = map_to_band(freq_min, freq_max)

        elec = extract_electrode(trend_name)
        if elec in ELECTRODE_CHAIN_REGIONS:
            hemi, _reg = ELECTRODE_CHAIN_REGIONS[elec]
            reg = ""

        entry = ColumnEntry(
            col_index=idx,
            code=code,
            i_group=i_group,
            sub_index=sub_index,
            trend_name=trend_name,
            family=family,
            frequency_band=band,
            freq_min_hz=freq_min,
            freq_max_hz=freq_max,
            hemisphere=hemi,
            region=reg,
            electrode=elec,
        )

        entry.resolution = resolution
        entry.mmx_name = mmx_inst.name if mmx_inst is not None else ""
        entry.sub_column_name = get_subcolumn_name(
            i_group, sub_index, trend_name, family,
            mmx_name=mmx_inst.name if mmx_inst is not None else None,
        )
        entry.common_name = generate_common_name(entry)

        entries.append(entry)

    entries.sort(key=lambda e: e.col_index)
    ensure_unique_common_names(entries)
    return entries


def get_columns_by_family(schema: list[ColumnEntry], family: str) -> list[ColumnEntry]:
    """Filter *schema* to entries whose ``family`` matches *family*."""
    return [e for e in schema if e.family == family]


def get_fft_power_columns(schema: list[ColumnEntry]) -> dict[str, dict[str, str]]:
    """Return a nested dict ``{band: {region_label: code}}`` for FFT Power columns.

    *region_label* is the original region substring from the trend name
    (e.g. ``"Left Anterior"``).  Only columns with ``family == "fft_power"``
    and a recognised frequency band are included.

    Example::

        {
            "delta": {"Left Anterior": "I34_1", "Left Posterior": "I35_1", ...},
            "theta": {...},
        }
    """
    result: dict[str, dict[str, str]] = {}

    for entry in schema:
        if entry.family != "fft_power" or not entry.frequency_band:
            continue

        # Reconstruct the region label from the trend name
        region_label = ""
        for candidate in ("Left Anterior", "Left Posterior", "Left Hemisphere",
                          "Right Anterior", "Right Posterior", "Right Hemisphere"):
            if candidate in entry.trend_name:
                region_label = candidate
                break

        if not region_label:
            continue

        result.setdefault(entry.frequency_band, {})[region_label] = entry.code

    return result
