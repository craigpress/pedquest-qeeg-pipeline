from __future__ import annotations
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class QCReport:
    patient_id: str = ""
    total_epochs: int = 0
    usable_epochs: int = 0
    artifact_pct: float = 0.0
    seizure_epochs: int = 0
    seizure_pct_of_total: float = 0.0
    recording_duration_hours: float = 0.0
    usable_hours: float = 0.0
    leading_zeros_removed: int = 0
    timestamp_gaps: int = 0
    median_suppression_pct: float | None = None
    bin_coverage: dict[str, float] = field(default_factory=dict)
    # Artifact-Reduction rejection (see qeeg.quality.ar_rejection). Distinct from
    # artifact_pct: that counts EXCLUDED EPOCHS, these count values that were
    # never measured. A partially-rejected epoch stays in the analysis with some
    # of its regions missing, so ar_rows_partial does not appear in artifact_pct.
    ar_rows_all_rejected: int = 0
    ar_rows_partial: int = 0
    ar_cells_nulled: int = 0
    ar_region_reject_pct: dict[str, float] = field(default_factory=dict)
    ar_segment_empty: bool = False
    # Columns that carried no information in this recording: zero-variance,
    # entirely missing, or identical to another column. Reported, never
    # repaired -- these are faithfully transported vendor outputs, and the
    # analyst needs to see them before modelling. See
    # qeeg.quality.constant_columns.
    constant_columns: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def summary_line(self) -> str:
        return (f"Epochs: {self.usable_epochs}/{self.total_epochs} "
                f"({self.artifact_pct:.1f}% artifact) | "
                f"Duration: {self.recording_duration_hours:.1f}h | "
                f"Seizure: {self.seizure_pct_of_total:.1f}%")

    def to_dict(self) -> dict:
        return {
            "patient_id": self.patient_id,
            "total_epochs": self.total_epochs,
            "usable_epochs": self.usable_epochs,
            "artifact_pct": self.artifact_pct,
            "seizure_epochs": self.seizure_epochs,
            "seizure_pct_of_total": self.seizure_pct_of_total,
            "recording_duration_hours": self.recording_duration_hours,
            "usable_hours": self.usable_hours,
            "leading_zeros_removed": self.leading_zeros_removed,
            "timestamp_gaps": self.timestamp_gaps,
            "median_suppression_pct": self.median_suppression_pct,
            "bin_coverage": self.bin_coverage,
            "ar_rows_all_rejected": self.ar_rows_all_rejected,
            "ar_rows_partial": self.ar_rows_partial,
            "ar_cells_nulled": self.ar_cells_nulled,
            "ar_region_reject_pct": self.ar_region_reject_pct,
            "ar_segment_empty": self.ar_segment_empty,
            "constant_columns": self.constant_columns,
            "warnings": self.warnings,
        }

def build_qc_report(patient_id: str, total_epochs: int, artifact_result,
                    seizure_mask: pd.Series | None, timestamps: pd.Series,
                    leading_zeros: int, gap_count: int,
                    ar_rejection=None,
                    epochs: pd.DataFrame | None = None) -> QCReport:
    """Build a QC report from processing results.

    ``epochs`` is optional so existing callers keep working; supply it to get
    the zero-variance / duplicate-column survey.
    """
    report = QCReport(patient_id=patient_id, total_epochs=total_epochs)
    if epochs is not None and len(epochs):
        from qeeg.quality.constant_columns import find_constant_columns
        const = find_constant_columns(epochs)
        report.constant_columns = const.to_dict()
        report.warnings.extend(const.warnings())
    if ar_rejection is not None:
        report.ar_rows_all_rejected = ar_rejection.rows_all_rejected
        report.ar_rows_partial = ar_rejection.rows_partial
        report.ar_cells_nulled = ar_rejection.cells_nulled
        report.ar_region_reject_pct = dict(ar_rejection.region_reject_pct)
        report.ar_segment_empty = ar_rejection.segment_empty
    report.leading_zeros_removed = leading_zeros
    report.timestamp_gaps = gap_count
    report.artifact_pct = artifact_result.artifact_pct
    report.usable_epochs = total_epochs - artifact_result.excluded_epochs - leading_zeros

    if seizure_mask is not None:
        report.seizure_epochs = int(seizure_mask.sum())
        report.seizure_pct_of_total = 100.0 * report.seizure_epochs / total_epochs if total_epochs > 0 else 0.0

    if len(timestamps) >= 2:
        duration = (timestamps.iloc[-1] - timestamps.iloc[0]).total_seconds() / 3600.0
        report.recording_duration_hours = duration
        # Estimate usable hours (usable_epochs * epoch_interval)
        if total_epochs > 1:
            epoch_interval_hours = duration / (total_epochs - 1)
            report.usable_hours = report.usable_epochs * epoch_interval_hours

    return report
