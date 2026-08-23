import { useState } from "react";
import { Upload, FileText, Loader2, CheckCircle, AlertCircle, ChevronDown, ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface UploadStatus {
  status: "idle" | "uploading" | "complete" | "error";
  message: string;
  count?: number;
}

interface Props {
  dragging: boolean;
  uploading: boolean;
  pathInput: string;
  onPathChange: (v: string) => void;
  onPathSubmit: () => void;
  onDrop: (e: React.DragEvent) => void;
  onDragOver: () => void;
  onDragLeave: () => void;
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  clinicalStatus: UploadStatus;
  correctionsStatus: UploadStatus;
  onClinicalUpload: (files: File[]) => void;
  onCorrectionsUpload: (files: File[]) => void;
  uploadError: string | null;
  onDismissUploadError: () => void;
}

function DropTarget({
  id,
  status,
  idleLabel,
  onClick,
  children,
}: {
  id: string;
  status: UploadStatus;
  idleLabel: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <div
      className="border-2 border-dashed border-border rounded p-3 cursor-pointer hover:bg-muted/20 transition"
      onClick={onClick}
    >
      {status.status === "uploading" ? (
        <div className="flex items-center gap-2 text-xs">
          <Loader2 className="h-4 w-4 animate-spin" />
          Uploading...
        </div>
      ) : status.status === "complete" ? (
        <div className="flex items-center gap-2 text-xs text-green-600">
          <CheckCircle className="h-4 w-4" />
          {status.message}
        </div>
      ) : status.status === "error" ? (
        <div className="flex items-center gap-2 text-xs text-red-600">
          <AlertCircle className="h-4 w-4" />
          {status.message}
        </div>
      ) : (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <FileText className="h-4 w-4" />
          {idleLabel}
        </div>
      )}
      {children}
    </div>
  );
}

export function ManualImportSection({
  dragging,
  uploading,
  pathInput,
  onPathChange,
  onPathSubmit,
  onDrop,
  onDragOver,
  onDragLeave,
  onFileSelect,
  clinicalStatus,
  correctionsStatus,
  onClinicalUpload,
  onCorrectionsUpload,
  uploadError,
  onDismissUploadError,
}: Props) {
  const [open, setOpen] = useState(false);
  const [hasDeidentifiedDates, setHasDeidentifiedDates] = useState(false);

  return (
    <Card>
      <CardHeader
        className="pb-2 cursor-pointer select-none"
        onClick={() => setOpen((v) => !v)}
      >
        <div className="flex items-center gap-2">
          {open ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
          <CardTitle className="text-sm">Manual File Import</CardTitle>
          <span className="text-xs text-muted-foreground">
            Clinical data, corrections, individual files
          </span>
        </div>
      </CardHeader>

      {open && (
        <CardContent className="space-y-4 pt-0">
          {/* Clinical Metadata */}
          <div className="space-y-2">
            <Label className="text-xs font-medium">Clinical Metadata CSV</Label>
            <p className="text-[10px] text-muted-foreground mb-2">
              Columns: patient_id, age_days, rosc_datetime (optional), notes (optional)
            </p>
            <DropTarget
              id="clinical-input"
              status={clinicalStatus}
              idleLabel="Click to select clinical data CSV"
              onClick={() => document.getElementById("clinical-input")?.click()}
            >
              <input
                id="clinical-input"
                type="file"
                accept=".csv"
                className="hidden"
                onChange={(e) => {
                  const f = Array.from(e.target.files || []);
                  if (f.length > 0) onClinicalUpload(f);
                  e.target.value = "";
                }}
              />
            </DropTarget>
          </div>

          {/* De-identified dates toggle */}
          <div className="flex items-center gap-2">
            <input
              id="deident-toggle"
              type="checkbox"
              checked={hasDeidentifiedDates}
              onChange={(e) => setHasDeidentifiedDates(e.target.checked)}
              className="h-3.5 w-3.5 accent-primary cursor-pointer"
            />
            <Label htmlFor="deident-toggle" className="text-xs cursor-pointer select-none">
              EEG dates are de-identified (PedQuEST)
            </Label>
          </div>

          {/* EEG Date Corrections */}
          {hasDeidentifiedDates && (
            <div>
              <Label className="text-xs font-medium">EEG Date Corrections CSV</Label>
              <p className="text-[10px] text-muted-foreground mt-1 mb-2">
                Columns: new_name, age_in_days_at_time_of_eeg, eeg_start_time, eeg_duration
              </p>
              <DropTarget
                id="corrections-input"
                status={correctionsStatus}
                idleLabel="Click to select EEG corrections CSV"
                onClick={() => document.getElementById("corrections-input")?.click()}
              >
                <input
                  id="corrections-input"
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={(e) => {
                    const f = Array.from(e.target.files || []);
                    if (f.length > 0) onCorrectionsUpload(f);
                    e.target.value = "";
                  }}
                />
              </DropTarget>
            </div>
          )}

          {/* File Path Input */}
          <div className="space-y-2">
            <Label className="text-xs font-medium">File Path (recommended for large files)</Label>
            <div className="flex gap-2">
              <Input
                value={pathInput}
                onChange={(e) => onPathChange(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") onPathSubmit(); }}
                placeholder="C:\path\to\patient_data.csv  (paste path or multiple paths separated by ;)"
                className="flex-1 h-8 text-xs font-mono"
              />
              <Button
                size="sm"
                className="h-8 text-xs"
                onClick={onPathSubmit}
                disabled={!pathInput.trim() || uploading}
              >
                {uploading ? <Loader2 className="h-3 w-3 animate-spin" /> : "Add"}
              </Button>
            </div>
            <p className="text-[10px] text-muted-foreground">
              Files stay on your computer — no upload. Paste full path, or separate multiple paths with ; or newlines.
            </p>
          </div>

          {/* Drop Zone */}
          <div
            className={`border-2 border-dashed rounded-lg transition-colors cursor-pointer p-6 ${
              dragging ? "border-primary bg-primary/5" : "border-border"
            }`}
            onDragOver={(e) => { e.preventDefault(); onDragOver(); }}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            onClick={() => document.getElementById("file-input")?.click()}
          >
            <div className="flex flex-col items-center justify-center gap-2">
              {uploading ? (
                <Loader2 className="h-6 w-6 text-muted-foreground animate-spin" />
              ) : (
                <Upload className="h-6 w-6 text-muted-foreground" />
              )}
              <div className="text-center">
                <p className="text-xs font-medium">Drop CSV files here or click to browse</p>
                <p className="text-[10px] text-muted-foreground mt-1">
                  For smaller files only — large files should use the path input above
                </p>
              </div>
              <input
                id="file-input"
                type="file"
                accept=".csv"
                multiple
                className="hidden"
                onChange={onFileSelect}
              />
            </div>
          </div>

          {/* Upload error */}
          {uploadError && (
            <div className="flex items-center gap-2 p-3 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              <span>{uploadError}</span>
              <Button
                variant="ghost"
                size="sm"
                className="ml-auto h-6 text-[10px]"
                onClick={onDismissUploadError}
              >
                Dismiss
              </Button>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
