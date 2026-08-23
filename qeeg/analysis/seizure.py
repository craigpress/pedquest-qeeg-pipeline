from __future__ import annotations
import re as _re
import pandas as pd
import numpy as np
from dataclasses import dataclass, field


@dataclass
class SeizureReport:
    total_seizure_epochs: int = 0
    seizure_burden_pct: float = 0.0
    max_seizure_probability: float = 0.0
    seizure_events: int = 0  # number of distinct seizure episodes
    total_seizure_epochs_artifact_clean: int = 0
    seizure_events_artifact_clean: int = 0
    # Enhanced metrics (algorithmic screen, not adjudicated clinical diagnosis)
    max_hourly_burden_pct: float = 0.0       # max burden in any 1-hour sliding window
    has_status_epilepticus: bool = False      # algorithmic screen: continuous >=30 min OR >=50% of any 1h
    longest_seizure_minutes: float = 0.0     # duration of longest continuous seizure
    longest_seizure_minutes_artifact_clean: float = 0.0
    time_to_first_seizure_hours: float | None = None  # from reference (ROSC/recording start)
    time_to_first_seizure_hours_artifact_clean: float | None = None
    per_bin_burden: dict[str, float] = field(default_factory=dict)  # burden % per time bin

    @property
    def status_epilepticus_screen_flag(self) -> bool:
        """Canonical name for the algorithmic status-epilepticus screen.

        ``has_status_epilepticus`` is preserved as an alias for one release but
        its name falsely implies a clinically adjudicated ILAE diagnosis — this
        value is derived from Persyst seizure-trend output only."""
        return self.has_status_epilepticus

    def to_dict(self) -> dict:
        return {
            "total_seizure_epochs": self.total_seizure_epochs,
            "seizure_burden_pct": self.seizure_burden_pct,
            "max_seizure_probability": self.max_seizure_probability,
            "seizure_events": self.seizure_events,
            "total_seizure_epochs_artifact_clean": self.total_seizure_epochs_artifact_clean,
            "seizure_events_artifact_clean": self.seizure_events_artifact_clean,
            "max_hourly_burden_pct": self.max_hourly_burden_pct,
            "has_status_epilepticus": self.has_status_epilepticus,
            "status_epilepticus_screen_flag": self.has_status_epilepticus,
            "longest_seizure_minutes": self.longest_seizure_minutes,
            "longest_seizure_minutes_artifact_clean": self.longest_seizure_minutes_artifact_clean,
            "time_to_first_seizure_hours": self.time_to_first_seizure_hours,
            "time_to_first_seizure_hours_artifact_clean": self.time_to_first_seizure_hours_artifact_clean,
            "per_bin_burden": self.per_bin_burden,
        }


# P0-2: match the real Persyst labels, which are PLURAL ("Seizure Detections",
# "Seizure Notifications (P14)") and appear in no-space MMX-Name form
# ("SeizureProbabilityP14 Detections"). The prior singular, word-bounded pattern
# matched only the synthetic fixtures and silently no-op'd on real exports.
# Stems (probabilit/detect/notif) cover singular+plural; the second alternation
# covers the concatenated MMX names.
_SEIZURE_PATTERN = _re.compile(
    r'seizure\s*(probabilit|detect|notif|burden|mask)'
    r'|seizureprobabilit|seizuredetect|seizurenotif',
    _re.IGNORECASE,
)


def _is_seizure_column(description: str) -> bool:
    return bool(_SEIZURE_PATTERN.search(description))


def detect_seizure_columns(columns: list[str], code_to_desc: dict[str, str]) -> dict[str, str]:
    """Find seizure-related columns. Returns {role: column_code}."""
    result = {}
    for code, desc in code_to_desc.items():
        if code not in columns:
            continue
        if not _is_seizure_column(desc):
            continue
        desc_lower = desc.lower()
        if "probability" in desc_lower:
            result["probability"] = code
        elif "detection" in desc_lower:
            result["detections"] = code
        elif "notification" in desc_lower:
            result["notifications"] = code
    return result


def compute_seizure_mask(df: pd.DataFrame, seizure_columns: dict[str, str],
                         mode: str = "none", probability_threshold: float = 0.5) -> pd.Series:
    """Return boolean mask where True = seizure epoch.

    Modes:
    - none: no seizure detection (all False)
    - detected: use seizure detections column
    - probability: use probability >= threshold
    """
    mask = pd.Series(False, index=df.index)

    if mode == "none":
        return mask

    if mode == "detected" and "detections" in seizure_columns:
        col = seizure_columns["detections"]
        if col in df.columns:
            mask = df[col].fillna(0).astype(float) > 0

    elif mode == "probability" and "probability" in seizure_columns:
        col = seizure_columns["probability"]
        if col in df.columns:
            mask = df[col].fillna(0).astype(float) >= probability_threshold

    return mask


def compute_seizure_report(
    df: pd.DataFrame,
    seizure_columns: dict[str, str],
    seizure_mask: pd.Series,
    usable_mask: pd.Series | None = None,
    hours_relative: pd.Series | None = None,
    epoch_duration_sec: float = 1.0,
) -> SeizureReport:
    """Compute seizure summary statistics including ILAE status epilepticus flags.

    Args:
        df: Full epoch DataFrame
        seizure_columns: {role: column_code} from detect_seizure_columns
        seizure_mask: Boolean mask (True = seizure epoch)
        usable_mask: Boolean mask (True = interpretable epoch). If provided,
            burden is computed over usable time only (excluding artifact).
        hours_relative: Hours from reference for each epoch (for time-to-first-seizure)
        epoch_duration_sec: Duration of each epoch in seconds (default 1.0)
    """
    report = SeizureReport()
    total = len(df)

    report.total_seizure_epochs = int(seizure_mask.sum())
    clean_seizure_mask = seizure_mask & usable_mask if usable_mask is not None else seizure_mask.copy()
    report.total_seizure_epochs_artifact_clean = int(clean_seizure_mask.sum())

    # Burden over USABLE time (not total recording)
    if usable_mask is not None:
        usable_total = int(usable_mask.sum())
        seizure_in_usable = int((seizure_mask & usable_mask).sum())
    else:
        usable_total = total
        seizure_in_usable = report.total_seizure_epochs

    report.seizure_burden_pct = (
        100.0 * seizure_in_usable / usable_total if usable_total > 0 else 0.0
    )

    # Max probability
    if "probability" in seizure_columns:
        col = seizure_columns["probability"]
        if col in df.columns:
            report.max_seizure_probability = float(df[col].max())

    # Count distinct seizure events (transitions from non-seizure to seizure)
    if report.total_seizure_epochs > 0:
        transitions = seizure_mask.astype(int).diff().fillna(seizure_mask.astype(int))
        report.seizure_events = int((transitions == 1).sum())
    if report.total_seizure_epochs_artifact_clean > 0:
        clean_transitions = clean_seizure_mask.astype(int).diff().fillna(clean_seizure_mask.astype(int))
        report.seizure_events_artifact_clean = int((clean_transitions == 1).sum())

    # Time to first seizure
    if hours_relative is not None and report.total_seizure_epochs > 0:
        if seizure_mask.any():
            first_pos = int(seizure_mask.argmax())  # positional index of first True
            report.time_to_first_seizure_hours = float(hours_relative.iloc[first_pos])
        if clean_seizure_mask.any():
            first_clean_pos = int(clean_seizure_mask.argmax())
            report.time_to_first_seizure_hours_artifact_clean = float(hours_relative.iloc[first_clean_pos])

    # Longest continuous seizure (in minutes)
    if report.total_seizure_epochs > 0:
        runs = seizure_mask.astype(int)
        # Group consecutive same-value runs; filter to seizure runs only
        groups = (runs != runs.shift()).cumsum()
        run_lengths = runs.groupby(groups).sum()
        seizure_run_lengths = run_lengths[run_lengths > 0]
        longest_epochs = int(seizure_run_lengths.max()) if len(seizure_run_lengths) > 0 else 0
        report.longest_seizure_minutes = longest_epochs * epoch_duration_sec / 60.0
    if report.total_seizure_epochs_artifact_clean > 0:
        clean_runs = clean_seizure_mask.astype(int)
        clean_groups = (clean_runs != clean_runs.shift()).cumsum()
        clean_run_lengths = clean_runs.groupby(clean_groups).sum()
        clean_seizure_run_lengths = clean_run_lengths[clean_run_lengths > 0]
        longest_clean_epochs = int(clean_seizure_run_lengths.max()) if len(clean_seizure_run_lengths) > 0 else 0
        report.longest_seizure_minutes_artifact_clean = longest_clean_epochs * epoch_duration_sec / 60.0

    # Max hourly burden (1-hour sliding window)
    if total > 0:
        window_size = int(3600 / epoch_duration_sec)  # epochs per hour
        if window_size > 0 and total >= window_size:
            rolling_burden = (
                clean_seizure_mask.astype(float)
                .rolling(window=window_size, min_periods=window_size)
                .mean()
            )
            max_hourly_raw = rolling_burden.max()
            # N8: fallback when rolling produces all-NaN (recording shorter than 1 hour)
            if pd.isna(max_hourly_raw):
                report.max_hourly_burden_pct = report.seizure_burden_pct
            else:
                report.max_hourly_burden_pct = float(max_hourly_raw * 100.0)
        else:
            # Recording shorter than 1 hour — use full recording as window
            report.max_hourly_burden_pct = report.seizure_burden_pct

    # ILAE SE criterion 2: repeated seizures without interictal recovery
    # Proxy: any inter-seizure interval < 5 minutes (Trinka et al., Epilepsia 2015)
    repeated_without_recovery = False
    if report.seizure_events_artifact_clean >= 2 and hours_relative is not None and report.total_seizure_epochs_artifact_clean > 0:
        runs = clean_seizure_mask.astype(int)
        groups = (runs != runs.shift()).cumsum()
        seizure_onsets_hours: list[float] = []
        for _grp_id, grp_data in runs.groupby(groups):
            if grp_data.iloc[0] == 1:  # seizure run
                onset_pos = grp_data.index[0]
                # grp_data.index holds the DataFrame index labels; map via positional lookup
                seizure_onsets_hours.append(
                    float(hours_relative.iloc[seizure_mask.index.get_loc(onset_pos)])
                )
        if len(seizure_onsets_hours) >= 2:
            intervals_min = [
                (seizure_onsets_hours[i + 1] - seizure_onsets_hours[i]) * 60
                for i in range(len(seizure_onsets_hours) - 1)
            ]
            repeated_without_recovery = any(gap < 5.0 for gap in intervals_min)

    # ILAE 2015 SE criteria: (1) >=30 min, (2) repeated without recovery, (3) >=50% hourly burden
    report.has_status_epilepticus = (
        report.longest_seizure_minutes_artifact_clean >= 30.0
        or report.max_hourly_burden_pct >= 50.0
        or repeated_without_recovery
    )

    return report
