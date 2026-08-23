import { useState, useMemo } from "react";
import {
  ChevronDown,
  ChevronRight,
  CheckCircle,
  AlertTriangle,
  AlertCircle,
  FileText,
  Loader2,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { PatientManifestEntry, ManifestBuildResponse } from "@/types/api";

type ValidationStatus = "valid" | "warning" | "error";

function getStatus(patient: PatientManifestEntry): ValidationStatus {
  if (patient.validation_errors.length > 0) return "error";
  if (patient.validation_warnings.length > 0) return "warning";
  return "valid";
}

const STATUS_CONFIG: Record<
  ValidationStatus,
  { icon: typeof CheckCircle; color: string; badge: string; badgeClass: string }
> = {
  valid: {
    icon: CheckCircle,
    color: "text-emerald-500",
    badge: "Ready",
    badgeClass: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  },
  warning: {
    icon: AlertTriangle,
    color: "text-amber-500",
    badge: "Warnings",
    badgeClass: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  },
  error: {
    icon: AlertCircle,
    color: "text-red-500",
    badge: "Errors",
    badgeClass: "bg-red-500/15 text-red-400 border-red-500/30",
  },
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatDuration(hours: number): string {
  if (hours < 1) return `${(hours * 60).toFixed(0)}m`;
  return `${hours.toFixed(1)}h`;
}

interface ManifestReviewProps {
  manifest: ManifestBuildResponse;
  processing: boolean;
  studyName?: string;
  mmxStudy?: string;
  onProcess: (selectedPatientIds: string[]) => void;
}

export function ManifestReview({ manifest, processing, studyName, mmxStudy, onProcess }: ManifestReviewProps) {
  const [selected, setSelected] = useState<Set<string>>(() => {
    // Pre-select patients without errors
    const initial = new Set<string>();
    for (const p of manifest.patients) {
      if (p.validation_errors.length === 0) initial.add(p.patient_id);
    }
    return initial;
  });
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const selectableCount = manifest.patients.filter(
    (p) => p.validation_errors.length === 0,
  ).length;
  const allSelectableSelected = selected.size === selectableCount && selectableCount > 0;

  const summary = useMemo(() => {
    const sel = manifest.patients.filter((p) => selected.has(p.patient_id));
    return {
      patients: sel.length,
      files: sel.reduce((n, p) => n + p.persyst_files.length, 0),
      hours: sel.reduce((n, p) => n + p.total_duration_hours, 0),
    };
  }, [manifest.patients, selected]);

  function toggleSelectAll() {
    if (allSelectableSelected) {
      setSelected(new Set());
    } else {
      const next = new Set<string>();
      for (const p of manifest.patients) {
        if (p.validation_errors.length === 0) next.add(p.patient_id);
      }
      setSelected(next);
    }
  }

  function togglePatient(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleExpanded(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Scan Results</CardTitle>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span>{manifest.total_patients} patients</span>
            <span className="text-emerald-500">
              {manifest.validation_summary.valid ?? 0} ready
            </span>
            {(manifest.validation_summary.warnings ?? 0) > 0 && (
              <span className="text-amber-500">
                {manifest.validation_summary.warnings} warnings
              </span>
            )}
            {(manifest.validation_summary.errors ?? 0) > 0 && (
              <span className="text-red-500">
                {manifest.validation_summary.errors} errors
              </span>
            )}
          </div>
        </div>

        {/* Companion file status */}
        <div className="flex items-center gap-4 mt-2 text-xs">
          <span className="text-muted-foreground">
            Clinical CSV:{" "}
            {manifest.global_clinical_csv ? (
              <span className="text-emerald-400">found</span>
            ) : (
              <span className="text-muted-foreground/60">none</span>
            )}
          </span>
          <span className="text-muted-foreground">
            Corrections CSV:{" "}
            {manifest.global_corrections_csv ? (
              <span className="text-emerald-400">found</span>
            ) : (
              <span className="text-muted-foreground/60">none</span>
            )}
          </span>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Patient table */}
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-muted/50 text-xs text-muted-foreground">
                <th className="p-2 text-left w-10">
                  <input
                    type="checkbox"
                    checked={allSelectableSelected}
                    onChange={toggleSelectAll}
                    className="h-3.5 w-3.5 accent-primary cursor-pointer"
                  />
                </th>
                <th className="p-2 text-left w-6" />
                <th className="p-2 text-left">Patient ID</th>
                <th className="p-2 text-right">Files</th>
                <th className="p-2 text-right">Duration</th>
                <th className="p-2 text-right">Epochs</th>
                <th className="p-2 text-center">Status</th>
              </tr>
            </thead>
            <tbody>
              {manifest.patients.map((patient) => {
                const status = getStatus(patient);
                const cfg = STATUS_CONFIG[status];
                const Icon = cfg.icon;
                const isExpanded = expanded.has(patient.patient_id);
                const isSelected = selected.has(patient.patient_id);
                const hasError = status === "error";

                return (
                  <PatientRow
                    key={patient.patient_id}
                    patient={patient}
                    status={status}
                    cfg={cfg}
                    Icon={Icon}
                    isExpanded={isExpanded}
                    isSelected={isSelected}
                    hasError={hasError}
                    onToggleSelect={() => togglePatient(patient.patient_id)}
                    onToggleExpand={() => toggleExpanded(patient.patient_id)}
                  />
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Process button */}
        {selected.size > 0 && (
          <div className="flex items-center justify-between pt-1">
            <span className="text-xs text-muted-foreground">
              {summary.patients} patients, {summary.files} files,{" "}
              {formatDuration(summary.hours)} total
            </span>
            <Button
              onClick={() => onProcess(Array.from(selected))}
              disabled={processing || selected.size === 0}
              size="sm"
              className="gap-2"
            >
              {processing ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Processing...
                </>
              ) : (
                <>Process {selected.size} Patient{selected.size !== 1 ? "s" : ""}</>
              )}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** Single patient row + expandable detail */
function PatientRow({
  patient,
  status,
  cfg,
  Icon,
  isExpanded,
  isSelected,
  hasError,
  onToggleSelect,
  onToggleExpand,
}: {
  patient: PatientManifestEntry;
  status: ValidationStatus;
  cfg: (typeof STATUS_CONFIG)[ValidationStatus];
  Icon: typeof CheckCircle;
  isExpanded: boolean;
  isSelected: boolean;
  hasError: boolean;
  onToggleSelect: () => void;
  onToggleExpand: () => void;
}) {
  return (
    <>
      <tr
        className="hover:bg-muted/30 cursor-pointer transition-colors border-t border-border/50"
        onClick={onToggleExpand}
      >
        <td className="p-2" onClick={(e) => e.stopPropagation()}>
          <input
            type="checkbox"
            checked={isSelected}
            disabled={hasError}
            onChange={onToggleSelect}
            className="h-3.5 w-3.5 accent-primary cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
          />
        </td>
        <td className="p-2">
          {isExpanded ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
          )}
        </td>
        <td className="p-2 font-mono font-medium">{patient.patient_id}</td>
        <td className="p-2 text-right text-muted-foreground">
          {patient.persyst_files.length}
        </td>
        <td className="p-2 text-right font-mono text-muted-foreground">
          {formatDuration(patient.total_duration_hours)}
        </td>
        <td className="p-2 text-right font-mono text-muted-foreground">
          {patient.total_epochs.toLocaleString()}
        </td>
        <td className="p-2 text-center">
          <Badge variant="outline" className={`text-[9px] ${cfg.badgeClass}`}>
            <Icon className="h-3 w-3 mr-1" />
            {cfg.badge}
          </Badge>
        </td>
      </tr>

      {/* Expanded detail row */}
      {isExpanded && (
        <tr className="bg-muted/10">
          <td colSpan={7} className="px-4 py-3">
            <div className="space-y-2 text-xs">
              {/* Files list */}
              <div>
                <span className="text-muted-foreground font-medium">
                  Persyst files:
                </span>
                <ul className="mt-1 space-y-0.5 ml-4">
                  {patient.persyst_files.map((f) => (
                    <li key={f} className="flex items-center gap-2 text-muted-foreground">
                      <FileText className="h-3 w-3 flex-shrink-0" />
                      <span className="font-mono truncate">
                        {f.split(/[/\\]/).pop()}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Companion files */}
              <div className="flex items-center gap-4">
                <span className="text-muted-foreground">
                  Clinical:{" "}
                  {patient.clinical_csv ? (
                    <span className="text-emerald-400">
                      {patient.clinical_csv.split(/[/\\]/).pop()}
                    </span>
                  ) : (
                    <span className="text-muted-foreground/60">none</span>
                  )}
                </span>
                <span className="text-muted-foreground">
                  Corrections:{" "}
                  {patient.corrections_csv ? (
                    <span className="text-emerald-400">
                      {patient.corrections_csv.split(/[/\\]/).pop()}
                    </span>
                  ) : (
                    <span className="text-muted-foreground/60">none</span>
                  )}
                </span>
              </div>

              {/* Column counts */}
              {patient.n_columns_per_file.length > 1 && (
                <div className="text-muted-foreground">
                  Columns per file:{" "}
                  <span className="font-mono">
                    {patient.n_columns_per_file.join(", ")}
                  </span>
                </div>
              )}

              {/* Validation messages */}
              {patient.validation_errors.length > 0 && (
                <div className="space-y-1">
                  {patient.validation_errors.map((err, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 text-red-400 bg-red-500/10 rounded px-2 py-1"
                    >
                      <AlertCircle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
                      <span>{err}</span>
                    </div>
                  ))}
                </div>
              )}
              {patient.validation_warnings.length > 0 && (
                <div className="space-y-1">
                  {patient.validation_warnings.map((warn, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 text-amber-400 bg-amber-500/10 rounded px-2 py-1"
                    >
                      <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
                      <span>{warn}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
