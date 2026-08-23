"""Parse Persyst MMX trending configuration files.

Extracts engine cadence metadata (existing), Instrument definitions, and
Panel membership — the authoritative source for column → family/panel/channel
mapping in the ingestion pipeline.

MMX XML structure:
  <LTMPage>
    <Instruments>
      <Montage>          ← Engine definitions (EpochDuration/EpochStep present)
      <Instrument ...>   ← Instrument definitions (Name, Channels, InstanceID, optional <Engine RefId>)
      ...
    </Instruments>
    <Panel Name=...>     ← Panel membership (<Instrument Name=... InstanceID=.../>)
    ...
  </LTMPage>

Instruments may also appear inside Panel elements with full config (inline defs).
Engine back-references use <Engine RefId="..." EngineName="..."/>.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET

from qeeg.constants import ELECTRODE_NAME_MAP

logger = logging.getLogger(__name__)

# Compiled regex for normalizing old 10-20 electrode names in MMX Instrument Names.
# Applied at index-build time so lookups from normalize_electrode_names()-processed
# CSV headers always hit the index.
_INST_ELEC_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in ELECTRODE_NAME_MAP) + r")\b"
)


def _normalize_inst_name(name: str) -> str:
    """Normalize old 10-20 electrode names (T3→T7 etc.) in an MMX Instrument Name."""
    return _INST_ELEC_RE.sub(lambda m: ELECTRODE_NAME_MAP[m.group(0)], name)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class EngineConfig:
    """Configuration for a single Persyst calculation engine."""
    name: str
    epoch_duration: float  # seconds
    epoch_step: float      # seconds (update interval)
    ref_id: str = ""

    @property
    def rows_per_independent_obs(self) -> int:
        """Number of 1-second CSV rows per independent observation."""
        return max(1, int(round(self.epoch_step)))

    @property
    def has_overlapping_windows(self) -> bool:
        """True if windows overlap (epoch_duration > epoch_step)."""
        return self.epoch_duration > self.epoch_step


@dataclass
class InstrumentDef:
    """A single Persyst Instrument definition from the MMX file.

    The ``name`` field matches the trend name as it appears in Persyst CSV
    exports and is the primary key for column-to-family resolution.
    """
    name: str
    instance_id: str
    channels: str           # e.g. "Left Anterior", "Asym Hemi", "All 10-20", ""
    graph_title: str
    freq_min: Optional[float]
    freq_max: Optional[float]
    engine: Optional[EngineConfig]  # None for computed/display instruments
    family: str             # inferred from Name prefix (see _infer_family)
    panels: list[str] = field(default_factory=list)  # panel names this appears in


@dataclass
class PanelDef:
    """A Persyst Panel (display tab) and its ordered instrument list."""
    name: str
    instruments: list[InstrumentDef]  # in display order


@dataclass
class MMXConfig:
    """Full parsed MMX configuration.

    engines         : {engine_name: EngineConfig} — by EngineName
    engines_by_ref  : {ref_id: EngineConfig}      — for RefId resolution
    instruments     : {instrument_name: InstrumentDef}  — canonical key
    instance_index  : {instance_id: InstrumentDef}      — by InstanceID
    panels          : {panel_name: PanelDef}
    mmx_version     : LTMPage Version attribute (e.g. "15")
    mmx_path        : source file path
    """
    engines: dict[str, EngineConfig]
    engines_by_ref: dict[str, EngineConfig]
    instruments: dict[str, InstrumentDef]
    instance_index: dict[str, InstrumentDef]
    panels: dict[str, PanelDef]
    mmx_version: str
    mmx_path: str


# ---------------------------------------------------------------------------
# Family inference from Instrument Name
# ---------------------------------------------------------------------------

# Order matters: more-specific patterns before generic ones.
_FAMILY_PATTERNS: list[tuple[re.Pattern, str]] = [
    # FFT derived — ratio variants first
    (re.compile(r"FFT_PowerRatio\s+6-14", re.I),       "alpha_variability"),  # RAV
    (re.compile(r"FFT_PowerRatio\s+8-13",  re.I),       "adr"),               # ADR
    (re.compile(r"FFT_PowerRatio",          re.I),       "fft_power_ratio"),   # other ratios
    # Time Avg wrappers carry the inner name — delegate to inner parse
    (re.compile(r"Time Avg\s*<[^>]+>\s*\[FFT_PowerRatio\s+6-14", re.I), "alpha_variability"),
    (re.compile(r"Time Avg\s*<[^>]+>\s*\[FFT_PowerRatio\s+8-13",  re.I), "adr"),
    (re.compile(r"Time Avg\s*<[^>]+>\s*\[FFT_PowerRatio",          re.I), "fft_power_ratio"),
    (re.compile(r"Time Avg\s*<[^>]+>\s*\[FFT_Power\b",             re.I), "fft_power"),
    (re.compile(r"Time Avg",                re.I),       "time_average"),
    # FFT primary
    (re.compile(r"FFT_Spectrogram",         re.I),       "fft_spectrogram"),
    (re.compile(r"FFT_Power\b",             re.I),       "fft_power"),
    (re.compile(r"FFT_Edge",                re.I),       "spectral_edge"),
    # Asymmetry
    (re.compile(r"Asymmetry,\s*Relative\s*Spectrogram", re.I), "asymmetry_spectrogram"),
    (re.compile(r"Asymmetry,\s*(Relative|Absolute)\s*Index", re.I), "asymmetry"),
    (re.compile(r"Asymmetry",               re.I),       "asymmetry"),
    # Rhythmicity
    (re.compile(r"Rhythmicity\s*Spectrogram", re.I),    "rhythmicity_spectrogram"),
    (re.compile(r"SumValues",               re.I),       "rhythmicity"),
    (re.compile(r"Rhythmicity",             re.I),       "rhythmicity"),
    # aEEG / BSR
    (re.compile(r"^aEEG\b",                re.I),        "aeeg"),
    (re.compile(r"^BSR\b",                 re.I),        "suppression_ratio"),
    # Artifact / quality
    (re.compile(r"ArtifactIntensity",       re.I),       "artifact_intensity"),
    (re.compile(r"ElectrodeSignalQuality",  re.I),       "electrode_quality"),
    (re.compile(r"ArtifactDetector",        re.I),       "artifact_detector"),
    # Status Epilepticus & Seizure Burden (Persyst-native metrics, V8+) — before seizure
    (re.compile(r"Status\s+Epilepticus",    re.I),       "status_epilepticus"),
    (re.compile(r"Seizure\s+Burden",        re.I),       "seizure_burden"),
    # Seizure
    (re.compile(r"SeizureProbabilityP14\s+Probability", re.I), "seizure_probability"),
    (re.compile(r"SeizureProbabilityP14\s+Detections",  re.I), "seizure_detection"),
    (re.compile(r"SeizureProbabilityP14",   re.I),       "seizure_probability"),
    # Spike density
    (re.compile(r"SpikeDensityV1\b",        re.I),       "spike_density"),
    (re.compile(r"EventDensity\s+Spike",    re.I),       "spike_density"),
    (re.compile(r"EventDensity\s+SpikeBurst", re.I),     "spike_density"),
    (re.compile(r"EventDensity\s+SpikeGen", re.I),       "spike_density"),
    # Periodic discharges (boolean expression instruments)
    (re.compile(r"Boolean\s+[LR][A-Z]D",   re.I),       "rhythmic_delta"),
    # Peak envelope
    (re.compile(r"PeakEnvelope",            re.I),       "peak_envelope"),
    # Sleep / RDA
    (re.compile(r"Rhythmic\s+Delta\s+Indicator", re.I), "rda"),
    (re.compile(r"Sleep",                   re.I),       "sleep"),
    # Heart rate
    (re.compile(r"Heart\s*Rate",            re.I),       "heart_rate"),
    # EKG
    (re.compile(r"EKG",                     re.I),       "heart_rate"),
    # Coherence
    (re.compile(r"Coherence",               re.I),       "coherence_spectrogram"),
    # Annotation / display
    (re.compile(r"^Comment",               re.I),        "annotation"),
    (re.compile(r"ColorScaledBars",        re.I),        "display"),
    (re.compile(r"^Time[,\s]",            re.I),         "time_display"),
]


def _infer_family(name: str) -> str:
    """Infer feature family from MMX Instrument Name.

    Power ratios are classified by denominator (relative power vs ADR/RAV) via
    column_mapper.classify_ratio — the numerator alone is ambiguous (e.g.
    8-13//1-4 is ADR but 8-13//1-30 is relative alpha power).
    """
    if re.search(r"FFT_PowerRatio", name, re.I):
        from qeeg.ingestion.column_mapper import classify_ratio
        family, _ = classify_ratio(name)
        return family
    for pattern, family in _FAMILY_PATTERNS:
        if pattern.search(name):
            return family
    return "other"


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _parse_engines(root: ET.Element) -> tuple[dict[str, EngineConfig], dict[str, EngineConfig]]:
    """Extract engine definitions from <Instruments>/<Montage> elements."""
    by_name: dict[str, EngineConfig] = {}
    by_ref: dict[str, EngineConfig] = {}

    for montage in root.findall(".//Instruments/Montage"):
        for eng_el in montage.findall("Engine"):
            name = eng_el.get("EngineName", "")
            ref_id = eng_el.get("RefId", "")
            epoch_dur_str = eng_el.get("EpochDuration")
            if not name or epoch_dur_str is None:
                continue
            cfg = EngineConfig(
                name=name,
                epoch_duration=float(epoch_dur_str),
                epoch_step=float(eng_el.get("EpochStep", "1")),
                ref_id=ref_id,
            )
            by_name[name] = cfg
            if ref_id:
                by_ref[ref_id] = cfg

    return by_name, by_ref


def _parse_instrument_el(
    el: ET.Element,
    engines_by_ref: dict[str, EngineConfig],
) -> Optional[InstrumentDef]:
    """Parse a single <Instrument> element into an InstrumentDef."""
    name = _normalize_inst_name(el.get("Name", "").strip())
    instance_id = el.get("InstanceID", "").strip()
    if not name or not instance_id:
        return None

    channels = el.get("Channels", "").strip()
    graph_title = el.get("GraphTitle", "").strip()
    freq_min_s = el.get("FreqMin")
    freq_max_s = el.get("FreqMax")
    freq_min = float(freq_min_s) if freq_min_s is not None else None
    freq_max = float(freq_max_s) if freq_max_s is not None else None

    # Resolve engine back-reference
    engine: Optional[EngineConfig] = None
    eng_ref_el = el.find("Engine")
    if eng_ref_el is not None:
        ref_id = eng_ref_el.get("RefId", "")
        engine = engines_by_ref.get(ref_id)
        if ref_id and engine is None:
            logger.warning("MMX: Instrument %r references unknown Engine RefId=%r", name, ref_id)

    return InstrumentDef(
        name=name,
        instance_id=instance_id,
        channels=channels,
        graph_title=graph_title,
        freq_min=freq_min,
        freq_max=freq_max,
        engine=engine,
        family=_infer_family(name),
    )


def _parse_instruments(
    root: ET.Element,
    engines_by_ref: dict[str, EngineConfig],
) -> tuple[dict[str, InstrumentDef], dict[str, InstrumentDef]]:
    """Extract Instrument definitions from <Instruments> section.

    Returns (by_name, by_instance_id). When names collide the last definition
    wins (Persyst occasionally repeats an instrument with refinements).
    """
    by_name: dict[str, InstrumentDef] = {}
    by_id: dict[str, InstrumentDef] = {}

    instruments_el = root.find("Instruments")
    if instruments_el is None:
        return by_name, by_id

    # Instruments live inside <Montage> elements (or directly under <Instruments>)
    for container in [instruments_el] + list(instruments_el.findall("Montage")):
        for el in container:
            if el.tag != "Instrument":
                continue
            defn = _parse_instrument_el(el, engines_by_ref)
            if defn is None:
                continue
            by_name[defn.name] = defn
            by_id[defn.instance_id] = defn

    return by_name, by_id


def _parse_panels(
    root: ET.Element,
    by_name: dict[str, InstrumentDef],
    by_id: dict[str, InstrumentDef],
    engines_by_ref: dict[str, EngineConfig],
) -> dict[str, PanelDef]:
    """Extract Panel definitions.

    Panel <Instrument> children are references (Name + InstanceID only) back to
    the full definitions in <Instruments>.  Some panels also contain inline full
    definitions (e.g. a one-off REASI instrument) — those are parsed and added
    to both indexes.
    """
    panels: dict[str, PanelDef] = {}

    for panel_el in root.findall("Panel"):
        panel_name = panel_el.get("Name", "").strip()
        if not panel_name:
            continue

        members: list[InstrumentDef] = []
        for el in panel_el:
            if el.tag != "Instrument":
                continue
            ref_name = el.get("Name", "").strip()
            ref_iid = el.get("InstanceID", "").strip()

            # Try to resolve reference → existing definition
            defn: Optional[InstrumentDef] = by_id.get(ref_iid) or by_name.get(ref_name)

            if defn is None:
                # Inline definition with full attributes
                if el.get("Channels") is not None or el.get("GraphTitle") is not None:
                    defn = _parse_instrument_el(el, engines_by_ref)
                    if defn:
                        by_name.setdefault(defn.name, defn)
                        by_id.setdefault(defn.instance_id, defn)
                else:
                    logger.debug(
                        "MMX Panel %r: reference to unknown Instrument Name=%r InstanceID=%r",
                        panel_name, ref_name, ref_iid,
                    )
                    continue

            if defn is not None:
                members.append(defn)
                if panel_name not in defn.panels:
                    defn.panels.append(panel_name)

        panels[panel_name] = PanelDef(name=panel_name, instruments=members)

    return panels


def parse_mmx(path: str | Path) -> MMXConfig:
    """Parse a Persyst MMX file and return the full configuration.

    Returns:
        MMXConfig with engines, instruments (keyed by Name and InstanceID),
        and panels.  Replaces the old dict[str, EngineConfig] return type.
    """
    path = Path(path)
    tree = ET.parse(path)
    root = tree.getroot()

    mmx_version = root.get("Version", "")

    engines_by_name, engines_by_ref = _parse_engines(root)
    instruments_by_name, instruments_by_id = _parse_instruments(root, engines_by_ref)
    panels = _parse_panels(root, instruments_by_name, instruments_by_id, engines_by_ref)

    logger.debug(
        "MMX parsed: %s — %d engines, %d instruments, %d panels",
        path.name,
        len(engines_by_name),
        len(instruments_by_name),
        len(panels),
    )

    return MMXConfig(
        engines=engines_by_name,
        engines_by_ref=engines_by_ref,
        instruments=instruments_by_name,
        instance_index=instruments_by_id,
        panels=panels,
        mmx_version=mmx_version,
        mmx_path=str(path),
    )


# ---------------------------------------------------------------------------
# Backwards-compatibility shim
# ---------------------------------------------------------------------------

def parse_mmx_engines_only(path: str | Path) -> dict[str, EngineConfig]:
    """Legacy interface — returns only engine configs keyed by name.

    Callers that used the old parse_mmx() return type can use this until
    they are updated to consume MMXConfig.
    """
    cfg = parse_mmx(path)
    return cfg.engines
