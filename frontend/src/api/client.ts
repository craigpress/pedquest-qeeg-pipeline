/** Typed API client for the qEEG FastAPI backend. */
import type {
  UploadResponse,
  PipelineRunRequest,
  PipelineRunResponse,
  PipelineProgress,
  BatchRunResponse,
  PatientSummary,
  ColumnEntry,
  EpochData,
  SpectrogramData,
  BinSummary,
  OverlayData,
  ComparisonData,
  ScanResponse,
  ScannedFile,
  ManifestBuildResponse,
  ChartMetadata,
  MmxUploadResponse,
  MmxConfigSummary,
  StudyInfo,
} from "@/types/api";

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { signal, ...init });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

// -- Upload --

export async function registerLocalPaths(paths: string[]): Promise<UploadResponse[]> {
  return request("/upload/local", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paths }),
  });
}

export async function uploadFiles(files: File[]): Promise<UploadResponse[]> {
  const form = new FormData();
  for (const f of files) {
    form.append("files", f);
  }
  const res = await fetch(`${BASE}/upload`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

// -- Pipeline --

export async function runPipeline(req: PipelineRunRequest): Promise<PipelineRunResponse> {
  return request("/pipeline/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export interface ReprocessConfig {
  artifact_mode: string;
  artifact_intensity_threshold: number;
  artifact_quality_threshold: number;
  seizure_mode: string;
  seizure_probability_threshold: number;
  bin_edges_hours: number[];
  min_coverage_hours: number;
}

export async function reprocessPatient(
  patientId: string,
  config: ReprocessConfig,
): Promise<PipelineRunResponse> {
  return request(`/pipeline/reprocess/${encodeURIComponent(patientId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
}

export function subscribePipelineStatus(
  jobId: string,
  onProgress: (p: PipelineProgress) => void,
  onComplete: (p: PipelineProgress) => void,
  onError: (err: string) => void,
): () => void {
  const es = new EventSource(`${BASE}/pipeline/status/${jobId}`);

  es.addEventListener("progress", (e) => {
    const data: PipelineProgress = JSON.parse(e.data);
    if (data.complete) {
      if (data.error) {
        onError(data.error);
      } else {
        onComplete(data);
      }
      es.close();
    } else {
      onProgress(data);
    }
  });

  es.onerror = () => {
    onError("Connection to pipeline status stream lost");
    es.close();
  };

  return () => es.close();
}

// -- Batch --

export async function runBatch(patients: PipelineRunRequest[]): Promise<BatchRunResponse> {
  return request("/batch/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ patients }),
  });
}

export function subscribeBatchStatus(
  batchId: string,
  onProgress: (data: Record<string, unknown>) => void,
  onComplete: () => void,
  onError?: (err: string) => void,
): () => void {
  const es = new EventSource(`${BASE}/batch/status/${batchId}`);

  es.addEventListener("progress", (e) => {
    onProgress(JSON.parse(e.data));
  });

  es.addEventListener("batch_complete", () => {
    onComplete();
    es.close();
  });

  es.onerror = () => {
    onError?.("Connection to batch status stream lost");
    es.close();
  };

  return () => es.close();
}

// -- Patients --

export async function listPatients(study?: string): Promise<PatientSummary[]> {
  const q = study ? `?study=${encodeURIComponent(study)}` : "";
  return request(`/patients${q}`);
}

export async function getPatient(patientId: string): Promise<PatientSummary> {
  return request(`/patients/${encodeURIComponent(patientId)}`);
}

export async function getPatientSchema(patientId: string): Promise<ColumnEntry[]> {
  return request(`/patients/${encodeURIComponent(patientId)}/schema`);
}

export async function getChartMetadata(patientId: string): Promise<ChartMetadata> {
  return request(`/patients/${encodeURIComponent(patientId)}/chart-metadata`);
}

export async function getEpochData(
  patientId: string,
  families: string[],
  columnFilter?: string,
  signal?: AbortSignal,
  columns?: string[],
): Promise<EpochData> {
  const q = families.join(",");
  let url = `/patients/${encodeURIComponent(patientId)}/epochs?families=${encodeURIComponent(q)}`;
  if (columnFilter) {
    url += `&column_filter=${encodeURIComponent(columnFilter)}`;
  }
  if (columns && columns.length > 0) {
    url += `&columns=${encodeURIComponent(columns.join(","))}`;
  }
  return request(url, undefined, signal);
}

export async function getSpectrogram(
  patientId: string,
  specType: "fft_left" | "fft_right" | "asymmetry" | "asymmetry_hemi" | "asymmetry_ant" | "asymmetry_post" | "asymmetry_temp" | "asymmetry_parasag" | "rhythmicity" | "coherence",
  signal?: AbortSignal,
): Promise<SpectrogramData> {
  return request(`/patients/${encodeURIComponent(patientId)}/spectrogram/${specType}`, undefined, signal);
}

export async function getBinSummary(patientId: string): Promise<BinSummary> {
  return request(`/patients/${encodeURIComponent(patientId)}/bins`);
}

export async function getOverlayData(patientId: string, signal?: AbortSignal): Promise<OverlayData> {
  return request(`/patients/${encodeURIComponent(patientId)}/overlay`, undefined, signal);
}

// -- Compare --

export async function comparePatients(patientIds: string[]): Promise<ComparisonData> {
  const q = patientIds.join(",");
  return request(`/compare?ids=${encodeURIComponent(q)}`);
}

// -- Export --

export type ExportFormat = "csv" | "xlsx" | "json" | "parquet" | "wide" | "long" | "semilong" | "codebook";

export function getExportUrl(patientId: string, fmt: ExportFormat): string {
  return `${BASE}/export/${encodeURIComponent(patientId)}/${fmt}`;
}

export async function downloadExport(
  patientId: string,
  fmt: ExportFormat,
): Promise<void> {
  const url = getExportUrl(patientId, fmt);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${patientId}.${fmt}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

export async function downloadResearchPackage(
  patientId: string,
  includeGroups?: string[],
): Promise<void> {
  const res = await fetch(`${BASE}/export/${encodeURIComponent(patientId)}/package`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ include_groups: includeGroups ?? null }),
  });
  if (!res.ok) throw new Error(`Package download failed: ${res.status}`);
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${patientId}_research_package.zip`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
}

export async function deletePatient(patientId: string): Promise<{ deleted: string; cache_cleared: boolean }> {
  return request(`/patients/${encodeURIComponent(patientId)}`, { method: "DELETE" });
}

// -- Scan & Manifest --

export async function scanFolder(
  folderPath: string,
  recursive = true,
): Promise<ScanResponse> {
  return request("/scan/folder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder_path: folderPath, recursive }),
  });
}

/**
 * SSE-based folder scan. Calls onProgress with {classified, total, cached} for
 * each classified file, then resolves with the full ScanResponse on completion.
 */
export function scanFolderSSE(
  folderPath: string,
  onProgress: (classified: number, total: number, cached: boolean) => void,
  recursive = true,
): Promise<ScanResponse> {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({ folder_path: folderPath, recursive });
    // Use fetch + ReadableStream to POST and consume SSE
    fetch("/api/scan/folder/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    })
      .then((res) => {
        if (!res.ok || !res.body) {
          return res.text().then((t) => { throw new Error(t || res.statusText); });
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        function pump(): Promise<void> {
          return reader.read().then(({ done, value }) => {
            if (done) {
              reject(new Error("SSE stream closed before complete event"));
              return;
            }
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() ?? "";
            let eventType = "";
            for (const line of lines) {
              if (line.startsWith("event:")) {
                eventType = line.slice(6).trim();
              } else if (line.startsWith("data:")) {
                const data = line.slice(5).trim();
                if (eventType === "progress") {
                  try {
                    const p = JSON.parse(data) as { classified: number; total: number; cached: boolean };
                    onProgress(p.classified, p.total, p.cached ?? false);
                  } catch { /* ignore parse errors */ }
                } else if (eventType === "complete") {
                  try {
                    resolve(JSON.parse(data) as ScanResponse);
                  } catch (e) {
                    reject(e);
                  }
                  reader.cancel();
                  return;
                }
                eventType = "";
              }
            }
            return pump();
          });
        }
        return pump();
      })
      .catch(reject);
  });
}

export async function buildManifest(
  scannedFiles: ScannedFile[],
): Promise<ManifestBuildResponse> {
  return request("/manifest/build", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scanned_files: scannedFiles }),
  });
}

export async function uploadClinicalByPath(
  filePath: string,
): Promise<{ count: number }> {
  return request("/upload/clinical-path", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: filePath }),
  });
}

export async function uploadCorrectionsByPath(
  filePath: string,
): Promise<{ count: number }> {
  return request("/upload/corrections-path", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: filePath }),
  });
}

// -- MMX Configuration --

export async function uploadMmx(
  path: string,
  studyName: string,
): Promise<MmxUploadResponse> {
  return request("/upload/mmx", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, study_name: studyName }),
  });
}

export async function uploadMmxFile(
  file: File,
  studyName: string,
): Promise<MmxUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("study_name", studyName);
  return request("/upload/mmx/file", { method: "POST", body: form });
}

export async function listMmxConfigs(): Promise<MmxConfigSummary[]> {
  return request("/mmx/configs");
}

// -- Studies --

export async function listStudies(): Promise<StudyInfo[]> {
  return request("/studies");
}

export async function createStudy(
  name: string,
  mmxStudy?: string,
  dateShifted = false,
): Promise<StudyInfo> {
  return request("/studies", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, mmx_study: mmxStudy || null, date_shifted: dateShifted }),
  });
}

export async function deleteStudy(name: string): Promise<{ deleted: string; patients_unassigned: number }> {
  return request(`/studies/${encodeURIComponent(name)}`, { method: "DELETE" });
}

// -- Batch Export --

export async function downloadBatchResearchPackage(patientIds: string[]): Promise<void> {
  const res = await fetch(`${BASE}/export/batch-package`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ patient_ids: patientIds }),
  });
  if (!res.ok) throw new Error(`Batch package failed: ${res.status}`);
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "batch_research_package.zip";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
}

export async function downloadCohortParquet(patientIds: string[]): Promise<void> {
  const res = await fetch(`${BASE}/export/cohort`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ patient_ids: patientIds }),
  });
  if (!res.ok) throw new Error(`Cohort export failed: ${res.status}`);
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "cohort_dataset.zip";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
}

// -- Health --

export async function healthCheck(): Promise<{ status: string; patients_loaded: number }> {
  return request("/health");
}
