/** TypeScript types matching the Python Pydantic API models. */

export interface UploadResponse {
  file_id: string;
  patient_id: string;
  filename: string;
  size_bytes: number;
}

export interface PipelineRunRequest {
  file_ids: string[];
  patient_id?: string;
  rosc_time?: string;
  artifact_mode?: string;
  artifact_intensity_threshold?: number;
  artifact_quality_threshold?: number;
  seizure_mode?: string;
  seizure_probability_threshold?: number;
  bin_edges_hours?: number[];
  min_coverage_hours?: number;
  mmx_study?: string;
  study_name?: string;
}

export interface PipelineRunResponse {
  job_id: string;
  patient_id: string;
}

export interface PipelineProgress {
  job_id: string;
  patient_id: string;
  stage: string;
  progress: number;
  message: string;
  complete: boolean;
  error: string | null;
}

export interface BatchRunResponse {
  batch_id: string;
  jobs: PipelineRunResponse[];
}

export interface QCSummary {
  total_epochs: number;
  usable_epochs: number;
  artifact_pct: number;
  seizure_epochs: number;
  seizure_pct: number;
  recording_duration_hours: number;
  usable_hours: number;
  median_suppression_pct: number | null;
  bin_coverage: Record<string, number>;
  warnings: string[];
}

export interface SeizureSummary {
  total_seizure_epochs: number;
  seizure_burden_pct: number;
  max_seizure_probability: number;
  seizure_events: number;
  max_hourly_burden_pct: number;
  /** @deprecated The name implies ILAE status epilepticus; this is an algorithmic screen only. Prefer `status_epilepticus_screen_flag`. */
  has_status_epilepticus: boolean;
  status_epilepticus_screen_flag?: boolean;
  longest_seizure_minutes: number;
  time_to_first_seizure_hours: number | null;
  per_bin_burden: Record<string, number>;
}

export interface TimeAxisInfo {
  reference: string;
  reference_time: string;
  rosc_date: string | null;
  rosc_time: string | null;
  eeg_start_date: string | null;
  eeg_start_time: string | null;
  date_shifted: boolean;
  age_at_arrest_days: number | null;
  age_at_eeg_start_days: number | null;
  hours_rosc_to_eeg: number | null;
}

export interface PatientSummary {
  patient_id: string;
  qc: QCSummary;
  seizure: SeizureSummary;
  time_axis: TimeAxisInfo;
  n_columns: number;
  n_epochs: number;
  families: string[];
  study_name?: string;
}

export interface ColumnEntry {
  col_index: number;
  code: string;
  i_group: number;
  sub_index: number;
  trend_name: string;
  family: string;
  frequency_band: string;
  freq_min_hz: number | null;
  freq_max_hz: number | null;
  hemisphere: string;
  region: string;
  electrode: string;
  sub_column_name: string;
  common_name: string;
}

export interface EpochData {
  hours: number[];
  usable: boolean[];
  columns: Record<string, (number | null)[]>;
}

export interface SpectrogramData {
  frequencies: number[];
  hours: number[];
  matrix: (number | null)[][];
  colorscale: string;
}

export interface BinRow {
  bin_label: string;
  bin_start_hours: number;
  bin_end_hours: number;
  coverage_hours: number;
  coverage_fraction: number;
  n_observed: number;
  n_effective_fft: number;
  meets_minimum: boolean;
  background_continuity_index: number | null;
  seizure_burden_hours: number | null;
  missingness_flag: string;
  metrics: Record<string, number | null>;
}

export interface BinSummary {
  bins: BinRow[];
  bin_edges: number[];
}

export interface ArtifactRegion {
  start_hours: number;
  end_hours: number;
}

export interface OverlayData {
  artifact_regions: ArtifactRegion[];
  bin_boundaries: number[];
  gap_regions: ArtifactRegion[];
}

export interface ChartPanelMetadata {
  panel_id: string;
  display_name: string;
  description: string;
  source_families: string[];
  variables: string[];
  units: string;
  derivation: string;
  cadence_seconds: number;
  window_seconds: number;
  filtering: string;
}

export interface ChartMetadata {
  panels: ChartPanelMetadata[];
}

export interface ComparisonMetric {
  patient_id: string;
  metric_name: string;
  value: number | null;
  bin_label: string;
}

export interface ComparisonData {
  patient_ids: string[];
  metrics: ComparisonMetric[];
}

// ---------------------------------------------------------------------------
// Folder scan + manifest (S4/S6)
// ---------------------------------------------------------------------------

export type FileType =
  | "persyst_csv"
  | "clinical_csv"
  | "corrections_csv"
  | "raw_eeg"
  | "unknown";

export interface ScannedFile {
  path: string;
  filename: string;
  file_type: FileType;
  size_bytes: number;
  error: string | null;
  csv_panel_type?: string | null;
}

export interface ScanResponse {
  folder: string;
  files: ScannedFile[];
  counts: Record<string, number>;
}

export interface PatientManifestEntry {
  patient_id: string;
  persyst_files: string[];
  file_panel_types?: string[];
  clinical_csv: string | null;
  corrections_csv: string | null;
  raw_eeg_files: string[];
  total_duration_hours: number;
  total_epochs: number;
  n_columns_per_file: number[];
  validation_errors: string[];
  validation_warnings: string[];
  requires_corrections: boolean;
}

export interface ManifestBuildResponse {
  patients: PatientManifestEntry[];
  total_patients: number;
  global_clinical_csv: string | null;
  global_corrections_csv: string | null;
  validation_summary: Record<string, number>;
}

// ---------------------------------------------------------------------------
// MMX configuration (S7)
// ---------------------------------------------------------------------------

export interface MmxEngineEntry {
  name: string;
  epoch_duration: number;
  epoch_step: number;
  rows_per_independent_obs: number;
}

export interface MmxUploadResponse {
  study_name: string;
  fingerprint: string;
  engines: MmxEngineEntry[];
}

export interface MmxConfigSummary {
  study_name: string;
  fingerprint: string;
  source_path: string;
  n_engines: number;
  engines: MmxEngineEntry[];
}

// ---------------------------------------------------------------------------
// Study management
// ---------------------------------------------------------------------------

export interface StudyInfo {
  name: string;
  mmx_study: string | null;
  created_at: string | null;
  patient_count: number;
  date_shifted: boolean;
}
