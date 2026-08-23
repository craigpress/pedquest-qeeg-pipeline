import { useAppStore } from "@/stores/appStore";

function fmtHours(h: number) {
  const totalMin = Math.round(h * 60);
  const hh = Math.floor(totalMin / 60);
  const mm = totalMin % 60;
  return mm > 0 ? `${hh}h ${mm}m` : `${hh}h`;
}

export function RecordingHeader() {
  const summary = useAppStore((s) => s.patientSummary);

  if (!summary) return null;

  const { patient_id, qc, time_axis, study_name } = summary;
  const ingested = time_axis.eeg_start_date
    ? `${time_axis.eeg_start_date}${time_axis.eeg_start_time ? " " + time_axis.eeg_start_time : ""}`
    : time_axis.eeg_start_time ?? "—";

  return (
    <div className="flex items-center gap-4 px-4 py-2.5 border-b border-border bg-card">
      {/* Study identity */}
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="w-6 h-6 rounded text-[10px] font-mono font-semibold bg-muted flex items-center justify-center text-muted-foreground select-none shrink-0">
          {patient_id.slice(0, 2).toUpperCase()}
        </div>
        <div className="min-w-0">
          <span className="text-sm font-semibold truncate">{study_name ?? patient_id}</span>
          {study_name && study_name !== patient_id && (
            <span className="ml-1.5 text-xs font-mono text-muted-foreground">{patient_id}</span>
          )}
        </div>
      </div>

      <div className="w-px h-5 bg-border shrink-0" />

      {/* Metadata pills */}
      <div className="flex items-center gap-4 text-xs font-mono text-muted-foreground flex-wrap">
        {ingested !== "—" && (
          <span>
            <span className="text-muted-foreground/60 mr-1">INGESTED</span>
            <span className="text-foreground">{ingested}</span>
          </span>
        )}
        <span>
          <span className="text-muted-foreground/60 mr-1">DUR</span>
          <span className="text-foreground">{fmtHours(qc.recording_duration_hours)}</span>
        </span>
        <span>
          <span className="text-muted-foreground/60 mr-1">SOURCE</span>
          <span className="text-foreground">Persyst CSV</span>
        </span>
        {time_axis.reference === "rosc" && (
          <span className="bg-muted px-1.5 py-0.5 rounded text-[10px]">ROSC axis</span>
        )}
        {time_axis.date_shifted && (
          <span className="bg-muted px-1.5 py-0.5 rounded text-[10px]">Date-shifted</span>
        )}
      </div>
    </div>
  );
}
