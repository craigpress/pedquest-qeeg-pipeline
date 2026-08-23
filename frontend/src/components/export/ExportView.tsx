import { useState, useEffect } from "react";
import {
  Download,
  FileSpreadsheet,
  FileText,
  Table2,
  BookOpen,
  Database,
  ChevronDown,
  ChevronRight,
  Users,
  Package,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAppStore } from "@/stores/appStore";
import {
  downloadExport,
  downloadResearchPackage,
  downloadBatchResearchPackage,
  downloadCohortParquet,
  deletePatient,
  listPatients,
  listStudies,
} from "@/api/client";
import type { ExportFormat } from "@/api/client";
import type { StudyInfo } from "@/types/api";

interface FormatCard {
  fmt: ExportFormat;
  name: string;
  icon: React.ReactNode;
  description: string;
}

const FORMAT_DESCRIPTIONS: Record<string, string> = {
  semilong:
    "One row per time bin. Columns: patient_id, bin_label, bin_start_hours, bin_end_hours, coverage_fraction, meets_minimum, then one column per EEG feature (e.g. fft_delta_anterior_median, adr_posterior_median). Best for lme4/geepack mixed-effects models.",
  wide:
    "One row per patient. Columns: patient_id, then one column per feature × time bin (e.g. fft_delta_anterior_median_0-6h). Best for ML, logistic regression.",
  long:
    "One row per patient × bin × feature. Columns: patient_id, bin_label, variable_name, value, unit. Best for tidy analysis, ggplot2.",
  csv:
    "Time-bin summary with mapped variable names. Same structure as semilong.",
  xlsx:
    "Excel workbook with 3 sheets: Bin Summary, QC Report, Seizure Summary.",
  parquet:
    "Epoch-level data (all ~10-second epochs). One row per epoch × electrode. Best for LSTM / deep learning.",
  codebook:
    "JSON data dictionary: variable names, labels, units, families, and Stata-safe names.",
};

const FORMATS: FormatCard[] = [
  {
    fmt: "semilong",
    name: "Semi-Long CSV",
    icon: <Table2 className="h-5 w-5" />,
    description:
      "1 row per time bin, features as columns. For lme4/geepack mixed-effects models. Includes log-transformed, slopes, BCI.",
  },
  {
    fmt: "wide",
    name: "Wide CSV",
    icon: <Table2 className="h-5 w-5" />,
    description:
      "One row per patient, features \u00d7 bins as columns. For ML models, logistic regression.",
  },
  {
    fmt: "long",
    name: "Long CSV",
    icon: <FileText className="h-5 w-5" />,
    description:
      "One row per patient \u00d7 bin \u00d7 feature. For repeated-measures ANOVA, tidy workflows.",
  },
  {
    fmt: "csv",
    name: "Bins CSV",
    icon: <FileSpreadsheet className="h-5 w-5" />,
    description:
      "Time-binned summary statistics with mapped variable names.",
  },
  {
    fmt: "xlsx",
    name: "Excel",
    icon: <FileSpreadsheet className="h-5 w-5" />,
    description:
      "Multi-sheet workbook: Bin Summary, QC Report, Seizure Report.",
  },
  {
    fmt: "codebook",
    name: "Codebook",
    icon: <BookOpen className="h-5 w-5" />,
    description:
      "Data dictionary: variable names, labels, types, units. For R import.",
  },
  {
    fmt: "parquet",
    name: "Epochs (Parquet)",
    icon: <Database className="h-5 w-5" />,
    description:
      "Full epoch-level data for LSTM/transformer models.",
  },
];

export function ExportView() {
  const patientId = useAppStore((s) => s.patientId);
  const summary = useAppStore((s) => s.patientSummary);
  const [rGuideOpen, setRGuideOpen] = useState(false);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [batchDownloading, setBatchDownloading] = useState<string | null>(null);
  const [packageDownloading, setPackageDownloading] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [studies, setStudies] = useState<StudyInfo[]>([]);
  const [batchStudyFilter, setBatchStudyFilter] = useState<string>("");

  useEffect(() => {
    listStudies().then(setStudies).catch(() => {});
  }, []);

  const handleDownload = async (pid: string, fmt: ExportFormat) => {
    const key = `${pid}-${fmt}`;
    setDownloading(key);
    try {
      await downloadExport(pid, fmt);
    } finally {
      setDownloading(null);
    }
  };

  const handlePackageDownload = async (pid: string) => {
    setPackageDownloading(true);
    try {
      await downloadResearchPackage(pid);
    } finally {
      setPackageDownloading(false);
    }
  };

  const handleBatchDownload = async (fmt: ExportFormat) => {
    setBatchDownloading(fmt);
    try {
      const patients = await listPatients(batchStudyFilter || undefined);
      for (const p of patients) {
        await downloadExport(p.patient_id, fmt);
      }
    } finally {
      setBatchDownloading(null);
    }
  };

  const handleDelete = async (pid: string) => {
    try {
      await deletePatient(pid);
      setDeleteConfirm(false);
      // Navigate away from deleted patient
      useAppStore.getState().setPatient(null);
      useAppStore.getState().setView("patients");
    } catch (e) {
      console.error("Delete failed:", e);
    }
  };

  return (
    <div className="max-w-5xl mx-auto p-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Export Data</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Download analysis results for R/statistical analysis
        </p>
      </div>

      {/* Research Export Package */}
      {patientId && (
        <section>
          <Card className="border-primary/30 bg-primary/5">
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <Package className="h-5 w-5 text-primary" />
                <CardTitle className="text-base">Research Export Package</CardTitle>
                {summary && (
                  <Badge variant="secondary" className="font-mono text-xs ml-auto">
                    {summary.patient_id}
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground">
                ZIP bundle containing all export artifacts: epoch Parquet, bin summary CSV,
                semi-long CSV, provenance JSON (pipeline version, Persyst version, config,
                Python/pandas versions), column mapping CSV, and README with import guides
                for R, Python, and Stata.
              </p>
              <Button
                disabled={packageDownloading}
                onClick={() => handlePackageDownload(patientId)}
              >
                <Download className="h-4 w-4 mr-2" />
                {packageDownloading ? "Building Package..." : "Download Research Package (.zip)"}
              </Button>
            </CardContent>
          </Card>
        </section>
      )}

      {/* Section 1: Single Patient Export */}
      <section className="space-y-4">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold">Single Patient Export</h2>
          {patientId && summary && (
            <Badge variant="secondary" className="font-mono text-xs">
              {summary.patient_id}
            </Badge>
          )}
        </div>

        {!patientId ? (
          <Card>
            <CardContent className="flex items-center justify-center py-12 text-muted-foreground text-sm">
              Select a patient from the Patient List to enable single-patient exports.
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {FORMATS.map(({ fmt, name, icon, description }) => {
              const key = `${patientId}-${fmt}`;
              const isLoading = downloading === key;
              return (
                <Card key={fmt} className="flex flex-col">
                  <CardHeader className="pb-2">
                    <div className="flex items-center gap-2">
                      <div className="text-primary">{icon}</div>
                      <CardTitle className="text-sm">{name}</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent className="flex-1 flex flex-col justify-between gap-3">
                    <div className="space-y-2">
                      <CardDescription className="text-xs leading-relaxed">
                        {description}
                      </CardDescription>
                      {FORMAT_DESCRIPTIONS[fmt] && (
                        <div className="p-2 bg-muted/50 rounded text-xs text-muted-foreground leading-relaxed">
                          {FORMAT_DESCRIPTIONS[fmt]}
                        </div>
                      )}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full text-xs"
                      disabled={isLoading}
                      onClick={() => handleDownload(patientId, fmt)}
                    >
                      <Download className="h-3.5 w-3.5 mr-1.5" />
                      {isLoading ? "Downloading..." : "Download"}
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </section>

      {/* Section 2: Import Guides */}
      <section>
        <button
          onClick={() => setRGuideOpen(!rGuideOpen)}
          className="flex items-center gap-2 text-sm font-semibold hover:text-primary transition-colors"
        >
          {rGuideOpen ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
          Import Guides (R, Python, Stata)
        </button>
        {rGuideOpen && (
          <Card className="mt-3">
            <CardContent className="pt-4 space-y-4">
              <div>
                <p className="text-xs font-semibold text-muted-foreground mb-1">R (readr + arrow)</p>
                <pre className="text-xs font-mono bg-muted/50 rounded-md p-3 overflow-x-auto leading-relaxed">
{`library(readr); library(arrow)

# Semi-long: 1 row per bin, features as columns (for lme4/geepack)
semi_long <- read_csv("patient_semilong.csv")

# Wide: 1 row per patient, all features x bins as columns
wide <- read_csv("patient_wide.csv")

# Long: 1 row per patient x bin x feature
long <- read_csv("patient_long.csv")

# Epoch-level data (large, requires arrow)
epochs <- read_parquet("patient_epochs.parquet")

# Codebook
codebook <- jsonlite::fromJSON("patient_codebook.json")`}
                </pre>
              </div>
              <div>
                <p className="text-xs font-semibold text-muted-foreground mb-1">Python (pandas)</p>
                <pre className="text-xs font-mono bg-muted/50 rounded-md p-3 overflow-x-auto leading-relaxed">
{`import pandas as pd

semi_long = pd.read_csv("patient_semilong.csv")
epochs = pd.read_parquet("patient_epochs.parquet")
bins = pd.read_csv("patient_bins.csv")`}
                </pre>
              </div>
              <div>
                <p className="text-xs font-semibold text-muted-foreground mb-1">Stata</p>
                <pre className="text-xs font-mono bg-muted/50 rounded-md p-3 overflow-x-auto leading-relaxed">
{`import delimited "patient_semilong.csv", clear
describe
* Note: Variable names may be truncated. Use codebook for full names.
* Variable names are automatically shortened to ≤30 characters in the
* codebook's 'stata_name' field. Use the codebook export to get the
* Stata-safe name mapping before importing.`}
                </pre>
              </div>
            </CardContent>
          </Card>
        )}
      </section>

      {/* Section 3: Batch Export */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="h-5 w-5 text-muted-foreground" />
            <h2 className="text-lg font-semibold">Batch Export{batchStudyFilter ? ` (${batchStudyFilter})` : " (All Patients)"}</h2>
          </div>
          {studies.length > 0 && (
            <select
              value={batchStudyFilter}
              onChange={(e) => setBatchStudyFilter(e.target.value)}
              className="bg-background border border-border rounded px-2 py-1 text-xs"
            >
              <option value="">All patients</option>
              {studies.map((s) => (
                <option key={s.name} value={s.name}>
                  {s.name} ({s.patient_count} patients)
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Batch Research Package — primary option */}
        <Card className="border-primary/30 bg-primary/5">
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <Package className="h-5 w-5 text-primary" />
              <CardTitle className="text-base">Batch Research Package</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Single ZIP containing a complete research package for every processed patient.
              Each patient gets its own folder with epoch Parquet, bin summary CSV, semi-long CSV,
              provenance JSON, column mapping, and README with import guides.
            </p>
            <Button
              disabled={batchDownloading === "batch-package"}
              onClick={async () => {
                setBatchDownloading("batch-package");
                try {
                  const patients = await listPatients(batchStudyFilter || undefined);
                  await downloadBatchResearchPackage(patients.map((p) => p.patient_id));
                } finally {
                  setBatchDownloading(null);
                }
              }}
            >
              <Download className="h-4 w-4 mr-2" />
              {batchDownloading === "batch-package" ? "Building Package..." : "Download Batch Research Package (.zip)"}
            </Button>
          </CardContent>
        </Card>

        {/* Cohort Parquet + CSV formats */}
        <Card>
          <CardContent className="pt-6 space-y-4">
            <div className="space-y-3">
              <div>
                <p className="text-sm font-medium">Cohort Parquet Dataset</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Partitioned Parquet directory (one file per patient) with Arrow sidecar metadata
                  and manifest. Load as a single table with <code className="text-[10px]">arrow::open_dataset()</code> in R
                  or <code className="text-[10px]">pyarrow.dataset.dataset()</code> in Python.
                </p>
              </div>
              <Button
                variant="outline"
                disabled={batchDownloading === "cohort-parquet"}
                onClick={async () => {
                  setBatchDownloading("cohort-parquet");
                  try {
                    const patients = await listPatients(batchStudyFilter || undefined);
                    await downloadCohortParquet(patients.map((p) => p.patient_id));
                  } finally {
                    setBatchDownloading(null);
                  }
                }}
              >
                <Database className="h-4 w-4 mr-2" />
                {batchDownloading === "cohort-parquet" ? "Exporting..." : "Download Cohort Parquet (.zip)"}
              </Button>
            </div>

            <div className="border-t pt-3">
              <p className="text-sm font-medium mb-1">Per-Patient CSV Downloads</p>
              <p className="text-xs text-muted-foreground mb-3">
                Downloads each patient as a separate file (one per patient).
              </p>
              <div className="flex flex-wrap gap-3">
                {(["semilong", "wide", "long"] as ExportFormat[]).map((fmt) => {
                  const labels: Record<string, string> = {
                    semilong: "Semi-Long CSV",
                    wide: "Wide CSV",
                    long: "Long CSV",
                  };
                  return (
                    <Button
                      key={fmt}
                      variant="outline"
                      size="sm"
                      disabled={batchDownloading === fmt}
                      onClick={() => handleBatchDownload(fmt)}
                    >
                      <Download className="h-3.5 w-3.5 mr-1.5" />
                      {batchDownloading === fmt
                        ? "Exporting..."
                        : `Export All \u2014 ${labels[fmt]}`}
                    </Button>
                  );
                })}
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Section 4: Patient Management */}
      {patientId && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Patient Management</h2>
          <Card>
            <CardContent className="pt-6 space-y-3">
              {!deleteConfirm ? (
                <Button
                  variant="outline"
                  className="text-destructive border-destructive/30 hover:bg-destructive/10"
                  onClick={() => setDeleteConfirm(true)}
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete Patient Data
                </Button>
              ) : (
                <div className="flex items-center gap-3">
                  <p className="text-sm text-destructive">
                    Delete all cached data for {patientId}?
                  </p>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleDelete(patientId)}
                  >
                    Confirm Delete
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setDeleteConfirm(false)}
                  >
                    Cancel
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  );
}
