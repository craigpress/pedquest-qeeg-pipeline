import { useState, useEffect, useMemo } from "react";
import { Users, Trash2, Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  listPatients,
  getPatient,
  listStudies,
  deletePatient,
  deleteStudy,
} from "@/api/client";
import { useAppStore } from "@/stores/appStore";
import type { PatientSummary, StudyInfo } from "@/types/api";
import { formatStudyLabel } from "@/lib/studyLabel";

// ── Inline sparkline from per_bin_burden ──────────────────────────────────────
function BurdenSparkline({ burden }: { burden: Record<string, number> }) {
  const vals = Object.values(burden);
  if (vals.length === 0) return <span className="text-muted-foreground text-[10px]">—</span>;
  const max = Math.max(...vals, 0.001);
  const w = 80;
  const h = 20;
  const barW = Math.max(1, w / vals.length - 1);

  const maxVal = Math.max(...vals).toFixed(1);
  return (
    <svg
      width={w}
      height={h}
      className="overflow-visible"
      role="img"
      aria-label={`Seizure burden sparkline — peak ${maxVal}%`}
    >
      {vals.map((v, i) => {
        const barH = Math.max(1, (v / max) * h);
        return (
          <rect
            key={i}
            x={i * (barW + 1)}
            y={h - barH}
            width={barW}
            height={barH}
            fill={v > 5 ? "var(--destructive)" : "var(--chart-1)"}
            opacity={0.75}
          />
        );
      })}
    </svg>
  );
}

// ── Suppression ratio display ─────────────────────────────────────────────────
function SuppressionCell({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-muted-foreground text-[10px]">—</span>;
  const pct = Math.min(100, value);
  const color = pct > 50 ? "text-destructive" : pct > 20 ? "text-amber-500" : "text-muted-foreground";
  return (
    <span className={`text-xs font-mono ${color}`}>{pct.toFixed(1)}%</span>
  );
}

// ── Filter pill ───────────────────────────────────────────────────────────────
type FilterKey = "all" | "seizures" | "hi-artifact";

const FILTER_LABELS: Record<FilterKey, string> = {
  all: "All",
  seizures: "Seizures",
  "hi-artifact": "Hi-Artifact",
};

function matchesFilter(p: PatientSummary, f: FilterKey): boolean {
  if (f === "all") return true;
  if (f === "seizures") return p.seizure.seizure_events > 0;
  if (f === "hi-artifact") return p.qc.artifact_pct > 20;
  return true;
}

// ─────────────────────────────────────────────────────────────────────────────

export function PatientList() {
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [studies, setStudies] = useState<StudyInfo[]>([]);
  const [selectedStudy, setSelectedStudy] = useState<string>("");
  const [busy, setBusy] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<FilterKey>("all");

  const activePatientId = useAppStore((s) => s.patientId);
  const setPatient = useAppStore((s) => s.setPatient);
  const setView = useAppStore((s) => s.setView);
  const pipelineStatus = useAppStore((s) => s.pipelineStatus);

  useEffect(() => {
    loadPatients();
    loadStudies();
  }, []);

  useEffect(() => {
    if (pipelineStatus === "complete") {
      loadPatients();
      loadStudies();
    }
  }, [pipelineStatus]);

  useEffect(() => {
    loadPatients();
  }, [selectedStudy]);

  async function loadPatients() {
    setLoading(true);
    try {
      setPatients(await listPatients(selectedStudy || undefined));
    } catch (err) {
      console.error("Failed to load patients:", err);
    } finally {
      setLoading(false);
    }
  }

  async function loadStudies() {
    try {
      setStudies(await listStudies());
    } catch { /* ignore */ }
  }

  async function openPatient(pid: string) {
    const summary = await getPatient(pid);
    setPatient(pid, summary);
    setView("dashboard");
  }

  async function handleDeletePatient(pid: string, e: React.MouseEvent) {
    e.stopPropagation();
    if (!window.confirm(`Delete patient "${pid}"? This removes cached results but keeps the source CSV.`)) return;
    setBusy(pid);
    try {
      await deletePatient(pid);
      if (activePatientId === pid) setPatient(null, null);
      await loadPatients();
      await loadStudies();
    } catch (err) {
      window.alert(`Failed to delete patient: ${(err as Error).message}`);
    } finally {
      setBusy(null);
    }
  }

  async function handleDeleteStudy(name: string) {
    const study = studies.find((s) => s.name === name);
    const count = study?.patient_count ?? 0;
    const suffix = count > 0 ? ` ${count} patient${count !== 1 ? "s" : ""} will be unassigned.` : "";
    if (!window.confirm(`Delete study "${name}"?${suffix}`)) return;
    setBusy(`study:${name}`);
    try {
      await deleteStudy(name);
      if (selectedStudy === name) setSelectedStudy("");
      await loadStudies();
      await loadPatients();
    } catch (err) {
      window.alert(`Failed to delete study: ${(err as Error).message}`);
    } finally {
      setBusy(null);
    }
  }

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return patients.filter(
      (p) =>
        matchesFilter(p, filter) &&
        (q === "" || p.patient_id.toLowerCase().includes(q)),
    );
  }, [patients, filter, search]);

  // Count per filter for pills
  const counts = useMemo(
    () =>
      (["all", "seizures", "hi-artifact"] as FilterKey[]).reduce(
        (acc, k) => ({ ...acc, [k]: patients.filter((p) => matchesFilter(p, k)).length }),
        {} as Record<FilterKey, number>,
      ),
    [patients],
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full p-20 text-muted-foreground text-sm">
        Loading patients…
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 pt-5 pb-3 border-b border-border gap-4 flex-wrap">
        <div>
          <h1 className="text-base font-semibold">Patients</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {visible.length} of {patients.length} shown
            {selectedStudy && ` · ${formatStudyLabel(selectedStudy)}`}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Study filter */}
          <div className="flex items-center gap-1">
            <select
              value={selectedStudy}
              onChange={(e) => setSelectedStudy(e.target.value)}
              className="bg-background border border-border rounded px-2 py-1 text-xs h-7"
            >
              <option value="">All studies</option>
              {studies.map((s) => (
                <option key={s.name} value={s.name}>
                  {formatStudyLabel(s.name)} ({s.patient_count})
                </option>
              ))}
            </select>
            {selectedStudy && (
              <button
                type="button"
                disabled={busy === `study:${selectedStudy}`}
                onClick={() => handleDeleteStudy(selectedStudy)}
                className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                title={`Delete study "${selectedStudy}"`}
              >
                <Trash2 className="h-3 w-3" />
              </button>
            )}
          </div>

          <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => setView("import")}>
            Import More
          </Button>
        </div>
      </div>

      {/* Filter pills + search */}
      <div className="flex items-center gap-3 px-6 py-2 border-b border-border">
        <div className="flex items-center gap-1">
          {(["all", "seizures", "hi-artifact"] as FilterKey[]).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setFilter(k)}
              aria-pressed={filter === k}
              className={[
                "px-2.5 py-0.5 rounded-full text-[11px] font-medium transition-colors",
                filter === k
                  ? "bg-foreground text-background"
                  : "bg-muted text-muted-foreground hover:text-foreground",
              ].join(" ")}
            >
              {FILTER_LABELS[k]}
              <span className="ml-1 opacity-60">{counts[k]}</span>
            </button>
          ))}
        </div>

        <div className="relative ml-auto">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search patient ID…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-muted/50 border border-border rounded pl-6 pr-6 py-1 text-xs w-48 focus:outline-none focus:ring-1 focus:ring-ring"
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      {visible.length === 0 ? (
        <div className="flex flex-col items-center justify-center flex-1 gap-3 text-muted-foreground">
          <Users className="h-8 w-8 opacity-30" />
          <p className="text-sm">No patients match the current filter.</p>
          {(search || filter !== "all") && (
            <button
              type="button"
              onClick={() => { setSearch(""); setFilter("all"); }}
              className="text-xs underline hover:text-foreground"
            >
              Clear filters
            </button>
          )}
        </div>
      ) : (
        <div className="overflow-y-auto flex-1">
          <table className="w-full text-xs border-collapse">
            <thead className="sticky top-0 bg-card z-10">
              <tr className="border-b border-border">
                <th className="text-left px-4 py-2 font-medium text-muted-foreground uppercase tracking-wider text-[10px]">Patient ID</th>
                <th className="text-left px-3 py-2 font-medium text-muted-foreground uppercase tracking-wider text-[10px]">ROSC</th>
                <th className="text-left px-3 py-2 font-medium text-muted-foreground uppercase tracking-wider text-[10px]">Duration</th>
                <th className="text-left px-3 py-2 font-medium text-muted-foreground uppercase tracking-wider text-[10px]">Artifact</th>
                <th className="text-left px-3 py-2 font-medium text-muted-foreground uppercase tracking-wider text-[10px]">Seizure burden</th>
                <th className="text-left px-3 py-2 font-medium text-muted-foreground uppercase tracking-wider text-[10px]">Suppression</th>
                <th className="w-8 px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {visible.map((p) => {
                const roscLabel = p.time_axis?.date_shifted && p.time_axis.age_at_arrest_days != null
                  ? `Age ${p.time_axis.age_at_arrest_days}d`
                  : !p.time_axis?.date_shifted && p.time_axis?.rosc_date
                    ? `${p.time_axis.rosc_date} ${p.time_axis.rosc_time ?? ""}`.trim()
                    : "—";

                return (
                  <tr
                    key={p.patient_id}
                    onClick={() => openPatient(p.patient_id)}
                    className={[
                      "border-b border-border/50 hover:bg-muted/30 cursor-pointer transition-colors group",
                      activePatientId === p.patient_id ? "bg-muted/40" : "",
                    ].join(" ")}
                  >
                    <td className="px-4 py-2.5">
                      <span className="font-mono font-semibold">{p.patient_id}</span>
                      {(p.seizure.status_epilepticus_screen_flag ?? p.seizure.has_status_epilepticus) && (
                        <span
                          className="ml-1.5 text-[9px] bg-destructive/20 text-destructive px-1 rounded uppercase tracking-wide"
                          title="Algorithmic screen only — not an ILAE diagnosis"
                        >
                          SE*
                        </span>
                      )}
                      {p.study_name && (
                        <span className="ml-1.5 text-[9px] text-muted-foreground">{formatStudyLabel(p.study_name)}</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 font-mono text-muted-foreground">{roscLabel}</td>
                    <td className="px-3 py-2.5 font-mono">{p.qc.recording_duration_hours.toFixed(1)}h</td>
                    <td className={`px-3 py-2.5 font-mono ${p.qc.artifact_pct > 20 ? "text-amber-500" : "text-muted-foreground"}`}>
                      {p.qc.artifact_pct.toFixed(1)}%
                    </td>
                    <td className="px-3 py-2.5">
                      <BurdenSparkline burden={p.seizure.per_bin_burden} />
                    </td>
                    <td className="px-3 py-2.5">
                      <SuppressionCell value={p.qc.median_suppression_pct} />
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <button
                        type="button"
                        disabled={busy === p.patient_id}
                        onClick={(e) => handleDeletePatient(p.patient_id, e)}
                        className="p-1 rounded text-muted-foreground opacity-0 group-hover:opacity-100 hover:text-destructive hover:bg-destructive/10 transition-all disabled:opacity-40"
                        title={`Delete patient ${p.patient_id}`}
                        aria-label={`Delete patient ${p.patient_id}`}
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
