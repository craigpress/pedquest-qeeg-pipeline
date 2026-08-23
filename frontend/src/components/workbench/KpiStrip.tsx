import { useAppStore } from "@/stores/appStore";

interface KpiProps {
  label: string;
  value: string;
  sub?: string;
  hot?: boolean;
}

function Kpi({ label, value, sub, hot }: KpiProps) {
  return (
    <div
      className={[
        "flex flex-col gap-0.5 px-4 py-3 border-r border-border last:border-r-0 relative",
        hot ? "after:absolute after:top-0 after:left-0 after:right-0 after:h-0.5 after:bg-destructive" : "",
      ].join(" ")}
    >
      <span className="font-mono text-[9.5px] uppercase tracking-widest text-muted-foreground">
        {label}
      </span>
      <span
        className={[
          "font-mono text-xl font-medium leading-none tracking-tight",
          hot ? "text-destructive" : "text-foreground",
        ].join(" ")}
      >
        {value}
      </span>
      {sub && <span className="text-[11px] text-muted-foreground mt-0.5">{sub}</span>}
    </div>
  );
}

function fmtHhMm(h: number): string {
  const totalMin = Math.round(h * 60);
  const hh = Math.floor(totalMin / 60);
  const mm = totalMin % 60;
  return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
}

export function KpiStrip() {
  const summary = useAppStore((s) => s.patientSummary);

  if (!summary) return null;

  const { qc, seizure } = summary;
  const artifactHot = qc.artifact_pct > 20;

  return (
    <div className="grid border-b border-border" style={{ gridTemplateColumns: "repeat(6, 1fr)" }}>
      <Kpi label="Total Duration" value={fmtHhMm(qc.recording_duration_hours)} />
      <Kpi label="Usable Data" value={fmtHhMm(qc.usable_hours)} />
      <Kpi
        label="Artifact"
        value={`${qc.artifact_pct.toFixed(1)}%`}
        hot={artifactHot}
      />
      <Kpi
        label="Seizure Events"
        value={String(seizure.seizure_events)}
        sub={seizure.seizure_events > 0 ? `peak p=${seizure.max_seizure_probability.toFixed(2)}` : "none detected"}
      />
      <Kpi
        label="Suppression"
        value={qc.median_suppression_pct == null ? "n/a" : `${qc.median_suppression_pct.toFixed(1)}%`}
        sub="median SR"
      />
      <Kpi
        label="Usable Epochs"
        value={String(qc.usable_epochs)}
        sub={`of ${qc.total_epochs} total`}
      />
    </div>
  );
}
