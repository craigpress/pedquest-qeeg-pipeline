import { useAppStore } from "@/stores/appStore";

function fmtPct(pct: number, totalHours: number): string {
  const totalMin = pct * totalHours * 60;
  const h = Math.floor(totalMin / 60);
  const m = Math.floor(totalMin % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export function EventList() {
  const summary = useAppStore((s) => s.patientSummary);
  const setCursorPct = useAppStore((s) => s.setCursorPct);

  if (!summary) return <p className="text-xs text-muted-foreground px-1">No patient loaded.</p>;

  const { seizure, qc } = summary;
  // Match TimeAxis/Inspector denominator: timeline runs 0 (ROSC) → roscOffset + recording_duration.
  // time_to_first_seizure_hours is ROSC-relative, so the same denominator must apply.
  const roscOffset = Math.max(0, summary.time_axis?.hours_rosc_to_eeg ?? 0);
  const totalHours = roscOffset + qc.recording_duration_hours;

  if (seizure.seizure_events === 0) {
    return (
      <p className="text-xs text-muted-foreground px-1">No seizure events detected.</p>
    );
  }

  return (
    <div className="space-y-1.5">
      <p className="text-xs text-muted-foreground">
        {seizure.seizure_events} event{seizure.seizure_events !== 1 ? "s" : ""} detected.{" "}
        Peak p={seizure.max_seizure_probability.toFixed(2)}.
        {(seizure.status_epilepticus_screen_flag ?? seizure.has_status_epilepticus) && (
          <span
            className="ml-1 text-destructive font-medium"
            title="Algorithmic screen only — not an ILAE diagnosis"
          >
            Status screen (algorithmic).
          </span>
        )}
      </p>

      {/* Summary row — click to jump to first seizure */}
      {seizure.time_to_first_seizure_hours != null && (
        <button
          onClick={() =>
            setCursorPct(
              (seizure.time_to_first_seizure_hours ?? 0) / totalHours,
            )
          }
          className="w-full text-left flex items-center gap-2 px-2.5 py-2 rounded border border-border bg-background hover:border-muted-foreground text-xs transition-colors"
        >
          <span className="w-2 h-2 rounded-full bg-destructive shrink-0" />
          <span className="flex flex-col min-w-0">
            <span className="font-mono text-foreground">
              First: {seizure.time_to_first_seizure_hours.toFixed(1)}h
            </span>
            <span className="text-muted-foreground">Click to jump</span>
          </span>
          <span className="ml-auto font-mono text-muted-foreground">
            p {seizure.max_seizure_probability.toFixed(2)}
          </span>
        </button>
      )}

      <div className="text-[10px] text-muted-foreground space-y-0.5 pt-1">
        <div className="flex justify-between">
          <span>Longest seizure</span>
          <span className="font-mono">{seizure.longest_seizure_minutes.toFixed(1)} min</span>
        </div>
        <div className="flex justify-between">
          <span>Seizure burden</span>
          <span className="font-mono">{seizure.seizure_burden_pct.toFixed(1)}%</span>
        </div>
        <div className="flex justify-between">
          <span>Peak hourly burden</span>
          <span className="font-mono">{seizure.max_hourly_burden_pct.toFixed(1)}%</span>
        </div>
      </div>
    </div>
  );
}
