import { useState, useCallback, useRef } from "react";
import {
  uploadFiles,
  registerLocalPaths,
  runPipeline,
  subscribePipelineStatus,
  scanFolderSSE,
  buildManifest,
  runBatch,
  subscribeBatchStatus,
  uploadClinicalByPath,
  uploadCorrectionsByPath,
  uploadMmxFile,
  getPatient,
} from "@/api/client";
import { useAppStore } from "@/stores/appStore";
import { clearPatientDataCache } from "@/hooks/usePatientData";
import { StudySelector } from "./StudySelector";
import type { StudySelectorHandle } from "./StudySelector";
import { ManifestReview } from "./ManifestReview";
import { ScanFolderSection } from "./ScanFolderSection";
import { ManualImportSection } from "./ManualImportSection";
import { ImportQueue } from "./ImportQueue";
import type { FileEntry } from "./ImportQueue";
import type { UploadResponse, PipelineProgress, ManifestBuildResponse } from "@/types/api";

interface UploadStatus {
  status: "idle" | "uploading" | "complete" | "error";
  message: string;
  count?: number;
}

export function ImportView() {
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [pathInput, setPathInput] = useState("");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [mmxNotice, setMmxNotice] = useState<string | null>(null);
  const [clinicalStatus, setClinicalStatus] = useState<UploadStatus>({ status: "idle", message: "" });
  const [correctionsStatus, setCorrectionsStatus] = useState<UploadStatus>({ status: "idle", message: "" });
  const [folderPath, setFolderPath] = useState("");
  const [scanning, setScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState<{ classified: number; total: number } | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const [manifest, setManifest] = useState<ManifestBuildResponse | null>(null);
  const [batchProcessing, setBatchProcessing] = useState(false);
  const [selectedStudyName, setSelectedStudyName] = useState("");
  const [selectedMmxStudy, setSelectedMmxStudy] = useState<string | undefined>();
  const studySelectorRef = useRef<StudySelectorHandle>(null);

  const config = useAppStore((s) => s.config);
  const setPatient = useAppStore((s) => s.setPatient);
  const setView = useAppStore((s) => s.setView);
  const setPipelineStatus = useAppStore((s) => s.setPipelineStatus);

  const handleStudyChange = useCallback((name: string, mmx?: string) => {
    setSelectedStudyName(name);
    setSelectedMmxStudy(mmx);
  }, []);

  // ── File registration ─────────────────────────────────────────────────────

  async function doLocalRegister(paths: string[]) {
    setUploading(true);
    setUploadError(null);
    try {
      const results = await registerLocalPaths(paths);
      const entries: FileEntry[] = results.map((r) => ({
        upload: r,
        status: "uploaded",
        progress: 0,
        message: `Ready (${(r.size_bytes / (1024 * 1024)).toFixed(0)} MB)`,
      }));
      setFiles((prev) => [...prev, ...entries]);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setUploading(false);
    }
  }

  async function doUpload(rawFiles: File[]) {
    setUploading(true);
    setUploadError(null);
    try {
      const results = await uploadFiles(rawFiles);
      const entries: FileEntry[] = results.map((r) => ({
        upload: r as UploadResponse & { size_bytes: number },
        status: "uploaded",
        progress: 0,
        message: "Ready",
      }));
      setFiles((prev) => [...prev, ...entries]);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const all = Array.from(e.dataTransfer.files);

    // A dropped .mmx is a study config, not trend data — route it to the MMX
    // endpoint instead of rejecting it as "not a CSV".
    const mmx = all.filter((f) => f.name.toLowerCase().endsWith(".mmx"));
    if (mmx.length > 0) {
      setUploadError(null);
      try {
        for (const f of mmx) {
          await uploadMmxFile(f, selectedStudyName || "uploaded");
        }
        setMmxNotice(
          `Loaded ${mmx.length} MMX config as "${selectedStudyName || "uploaded"}".` +
            (selectedStudyName ? "" : " No study selected — pick one in Study to attach it."),
        );
      } catch (err) {
        setUploadError(err instanceof Error ? err.message : String(err));
      }
    }

    const dropped = all.filter((f) => f.name.toLowerCase().endsWith(".csv"));
    if (dropped.length === 0) {
      if (mmx.length === 0) setUploadError("Only .csv and .mmx files are supported.");
      return;
    }
    const paths = dropped.map((f) => (f as any).path).filter(Boolean);
    if (paths.length > 0) await doLocalRegister(paths);
    else await doUpload(dropped);
  }, [selectedStudyName]);

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || []);
    if (selected.length === 0) return;
    await doUpload(selected);
    e.target.value = "";
  }, []);

  async function handlePathSubmit() {
    if (!pathInput.trim()) return;
    const paths = pathInput
      .split(/[\n;]+/)
      .map((p) => p.trim().replace(/^["']|["']$/g, ""))
      .filter((p) => p.length > 0);
    if (paths.length === 0) return;
    await doLocalRegister(paths);
    setPathInput("");
  }

  // ── Pipeline processing ───────────────────────────────────────────────────

  const pipelineParams = () => ({
    artifact_mode: config.artifactMode,
    artifact_intensity_threshold: config.artifactThreshold,
    seizure_mode: config.seizureMode,
    seizure_probability_threshold: config.seizureThreshold,
    bin_edges_hours: config.binEdges,
    min_coverage_hours: config.minCoverageHours,
    rosc_time: config.roscTime || undefined,
  });

  async function processFile(index: number) {
    const entry = files[index];
    setFiles((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], status: "processing", progress: 0, message: "Starting..." };
      return next;
    });
    setPipelineStatus("running", 0, "Starting...");
    try {
      const resp = await runPipeline({ file_ids: [entry.upload.file_id], patient_id: entry.upload.patient_id, ...pipelineParams() });
      await new Promise<void>((resolve, reject) => {
        subscribePipelineStatus(
          resp.job_id,
          (p: PipelineProgress) => {
            setFiles((prev) => { const next = [...prev]; next[index] = { ...next[index], progress: p.progress, message: p.message }; return next; });
            setPipelineStatus("running", p.progress, p.message);
          },
          async () => {
            setFiles((prev) => { const next = [...prev]; next[index] = { ...next[index], status: "complete", progress: 1, message: "Done" }; return next; });
            setPipelineStatus("complete", 1, "Pipeline complete");
            clearPatientDataCache(resp.patient_id);
            setPatient(resp.patient_id, await getPatient(resp.patient_id));
            resolve();
          },
          (err: string) => {
            setFiles((prev) => { const next = [...prev]; next[index] = { ...next[index], status: "error", message: err }; return next; });
            setPipelineStatus("error", 0, err);
            reject(new Error(err));
          },
        );
      });
    } catch (err) {
      console.error("Pipeline failed:", err);
    }
  }

  async function processGroup(indices: number[]) {
    const entries = indices.map((i) => files[i]);
    const patientId = entries[0].upload.patient_id;
    indices.forEach((i) => setFiles((prev) => { const next = [...prev]; next[i] = { ...next[i], status: "processing", progress: 0, message: "Starting..." }; return next; }));
    setPipelineStatus("running", 0, "Starting...");
    try {
      const resp = await runPipeline({ file_ids: entries.map((e) => e.upload.file_id), patient_id: patientId, ...pipelineParams() });
      await new Promise<void>((resolve, reject) => {
        subscribePipelineStatus(
          resp.job_id,
          (p: PipelineProgress) => {
            indices.forEach((i) => setFiles((prev) => { const next = [...prev]; next[i] = { ...next[i], progress: p.progress, message: p.message }; return next; }));
            setPipelineStatus("running", p.progress, p.message);
          },
          async () => {
            indices.forEach((i) => setFiles((prev) => { const next = [...prev]; next[i] = { ...next[i], status: "complete", progress: 1, message: "Done" }; return next; }));
            setPipelineStatus("complete", 1, "Pipeline complete");
            clearPatientDataCache(resp.patient_id);
            setPatient(resp.patient_id, await getPatient(resp.patient_id));
            resolve();
          },
          (err: string) => {
            indices.forEach((i) => setFiles((prev) => { const next = [...prev]; next[i] = { ...next[i], status: "error", message: err }; return next; }));
            setPipelineStatus("error", 0, err);
            reject(new Error(err));
          },
        );
      });
    } catch (err) {
      console.error("Group pipeline failed:", err);
    }
  }

  async function processAll() {
    const groups = new Map<string, number[]>();
    files.forEach((f, i) => {
      if (f.status !== "uploaded") return;
      const pid = f.upload.patient_id;
      if (!groups.has(pid)) groups.set(pid, []);
      groups.get(pid)!.push(i);
    });
    for (const [, indices] of groups) {
      await (indices.length === 1 ? processFile(indices[0]) : processGroup(indices));
    }
    setView("patients");
  }

  // ── Auxiliary uploads ─────────────────────────────────────────────────────

  async function processClinicalUpload(rawFiles: File[]) {
    setClinicalStatus({ status: "uploading", message: "Uploading clinical data..." });
    try {
      const formData = new FormData();
      formData.append("file", rawFiles[0]);
      const resp = await fetch("/api/upload/clinical", { method: "POST", body: formData });
      if (!resp.ok) { setClinicalStatus({ status: "error", message: `Upload failed: ${await resp.text()}` }); return; }
      const data = await resp.json();
      setClinicalStatus({ status: "complete", message: `✓ Loaded clinical data for ${data.count} patients`, count: data.count });
    } catch (err) {
      setClinicalStatus({ status: "error", message: `Error: ${err instanceof Error ? err.message : "Upload failed"}` });
    }
  }

  async function processCorrectionsUpload(rawFiles: File[]) {
    setCorrectionsStatus({ status: "uploading", message: "Uploading corrections..." });
    try {
      const formData = new FormData();
      formData.append("file", rawFiles[0]);
      const resp = await fetch("/api/upload/eeg-corrections", { method: "POST", body: formData });
      if (!resp.ok) { setCorrectionsStatus({ status: "error", message: `Upload failed: ${await resp.text()}` }); return; }
      const data = await resp.json();
      setCorrectionsStatus({ status: "complete", message: `✓ Loaded corrections for ${data.count} file(s)`, count: data.count });
    } catch (err) {
      setCorrectionsStatus({ status: "error", message: `Error: ${err instanceof Error ? err.message : "Upload failed"}` });
    }
  }

  // ── Folder scan + batch ───────────────────────────────────────────────────

  async function handleScanFolder() {
    if (!folderPath.trim()) return;
    setScanning(true);
    setScanProgress(null);
    setScanError(null);
    setManifest(null);
    try {
      const cleanPath = folderPath.trim().replace(/^["']+|["']+$/g, "");
      const scanResult = await scanFolderSSE(cleanPath, (classified, total) => setScanProgress({ classified, total }));
      setScanProgress(null);
      if (scanResult.files.length === 0) { setScanError("No files found in the specified folder."); return; }
      setManifest(await buildManifest(scanResult.files));
    } catch (err) {
      setScanError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setScanning(false);
      setScanProgress(null);
    }
  }

  async function handleBatchProcess(selectedPatientIds: string[]) {
    if (!manifest) return;
    if (studySelectorRef.current) {
      const ok = await studySelectorRef.current.ensureStudyCreated();
      if (!ok) return;
    }
    const studyName = selectedStudyName || undefined;
    const mmxStudy = selectedMmxStudy;
    setBatchProcessing(true);
    setPipelineStatus("running", 0, "Preparing batch...");
    try {
      if (manifest.global_clinical_csv) { try { await uploadClinicalByPath(manifest.global_clinical_csv); } catch { /* non-fatal */ } }
      if (manifest.global_corrections_csv) { try { await uploadCorrectionsByPath(manifest.global_corrections_csv); } catch { /* non-fatal */ } }
      const selectedPatients = manifest.patients.filter((p) => selectedPatientIds.includes(p.patient_id));
      const batchRequests = [];
      for (const patient of selectedPatients) {
        const uploads = await registerLocalPaths(patient.persyst_files);
        batchRequests.push({ file_ids: uploads.map((u) => u.file_id), patient_id: patient.patient_id, ...pipelineParams(), mmx_study: mmxStudy, study_name: studyName });
      }
      const batchResp = await runBatch(batchRequests);
      subscribeBatchStatus(
        batchResp.batch_id,
        (data) => setPipelineStatus("running", typeof data.progress === "number" ? data.progress : 0, typeof data.message === "string" ? data.message : "Processing..."),
        async () => {
          setPipelineStatus("complete", 1, "Batch complete");
          for (const job of batchResp.jobs) clearPatientDataCache(job.patient_id);
          setBatchProcessing(false);
          setView("patients");
        },
        (errMsg) => { setPipelineStatus("error", 0, errMsg); setBatchProcessing(false); },
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Batch processing failed";
      console.error("Batch processing failed:", err);
      setPipelineStatus("error", 0, msg);
      setBatchProcessing(false);
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Data Import</h1>
        <p className="text-sm text-muted-foreground mt-1">Upload Persyst CSV exports for qEEG analysis</p>
      </div>

      <StudySelector ref={studySelectorRef} onStudyChange={handleStudyChange} />

      <ScanFolderSection
        folderPath={folderPath}
        onFolderPathChange={setFolderPath}
        scanning={scanning}
        scanProgress={scanProgress}
        scanError={scanError}
        onScan={handleScanFolder}
        onDismissError={() => setScanError(null)}
      />

      {manifest && (
        <ManifestReview
          manifest={manifest}
          processing={batchProcessing}
          studyName={selectedStudyName || undefined}
          mmxStudy={selectedMmxStudy}
          onProcess={handleBatchProcess}
        />
      )}

      <ManualImportSection
        dragging={dragging}
        uploading={uploading}
        pathInput={pathInput}
        onPathChange={setPathInput}
        onPathSubmit={handlePathSubmit}
        onDrop={handleDrop}
        onDragOver={() => setDragging(true)}
        onDragLeave={() => setDragging(false)}
        onFileSelect={handleFileSelect}
        clinicalStatus={clinicalStatus}
        correctionsStatus={correctionsStatus}
        onClinicalUpload={processClinicalUpload}
        onCorrectionsUpload={processCorrectionsUpload}
        uploadError={uploadError}
        onDismissUploadError={() => setUploadError(null)}
      />

      {mmxNotice && (
        <div
          className="text-xs text-emerald-400 bg-emerald-500/10 rounded px-2 py-1 cursor-pointer"
          onClick={() => setMmxNotice(null)}
        >
          {mmxNotice}
        </div>
      )}

      <ImportQueue
        files={files}
        onProcessAll={processAll}
        onViewPatients={() => setView("patients")}
      />
    </div>
  );
}
