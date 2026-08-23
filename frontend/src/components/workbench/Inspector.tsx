import { useState } from "react";
import { ChevronRight, ChevronLeft, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAppStore } from "@/stores/appStore";
import {
  getPatient,
  reprocessPatient,
  subscribePipelineStatus,
} from "@/api/client";
import { clearPatientDataCache } from "@/hooks/usePatientData";
import { EventList } from "./EventList";
import { PANELS } from "@/panels/manifest";

type Tab = "cursor" | "events" | "params";

const BIN_PRESETS: { label: string; edges: number[] }[] = [
  { label: "6h (0–72h)",    edges: [0, 6, 12, 18, 24, 48, 72] },
  { label: "6h (0–168h)",   edges: [0, 6, 12, 18, 24, 30, 36, 42, 48, 54, 60, 66, 72, 78, 84, 90, 96, 102, 108, 114, 120, 126, 132, 138, 144, 150, 156, 162, 168] },
  { label: "12h (0–72h)",   edges: [0, 12, 24, 36, 48, 60, 72] },
  { label: "24h (0–72h)",   edges: [0, 24, 48, 72] },
  { label: "Custom",        edges: [] },
];

function parseBinEdges(raw: string): number[] | null {
  const parts = raw.split(",").map((s) => s.trim()).filter(Boolean);
  if (parts.length < 2) return null;
  const nums = parts.map(Number);
  if (nums.some(isNaN)) return null;
  if (nums.some((n) => n < 0)) return null;
  for (let i = 1; i < nums.length; i++) {
    if (nums[i] <= nums[i - 1]) return null;
  }
  return nums;
}

function BinEdgesInput({
  value,
  onChange,
}: {
  value: number[];
  onChange: (edges: number[]) => void;
}) {
  const [raw, setRaw] = useState<string | null>(null);
  const [error, setError] = useState(false);

  const displayVal = raw ?? value.join(", ");
  const matchedPreset = BIN_PRESETS.find(
    (p) => p.edges.length > 0 && p.edges.join(",") === value.join(","),
  );
  const presetVal = matchedPreset ? matchedPreset.label : "Custom";

  return (
    <div className="space-y-1.5">
      <Select
        value={presetVal}
        onValueChange={(label) => {
          const preset = BIN_PRESETS.find((p) => p.label === label);
          if (preset && preset.edges.length > 0) {
            setRaw(null);
            setError(false);
            onChange(preset.edges);
          }
        }}
      >
        <SelectTrigger className="h-7 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {BIN_PRESETS.map((p) => (
            <SelectItem key={p.label} value={p.label}>
              {p.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <input
        className={[
          "w-full h-7 px-2 rounded border text-xs font-mono bg-background text-foreground",
          error
            ? "border-destructive focus:outline-none focus:ring-1 focus:ring-destructive"
            : "border-border focus:outline-none focus:ring-1 focus:ring-ring",
        ].join(" ")}
        value={displayVal}
        onChange={(e) => {
          setRaw(e.target.value);
          const parsed = parseBinEdges(e.target.value);
          setError(!parsed);
          if (parsed) onChange(parsed);
        }}
        onBlur={() => {
          if (!error) setRaw(null);
        }}
        placeholder="0, 6, 12, 24, 48, 72"
        spellCheck={false}
      />
      {error && (
        <p className="text-[10px] text-destructive">
          Must be ≥2 ascending non-negative numbers
        </p>
      )}
    </div>
  );
}

function useCursorReadout() {
  const activePanel = useAppStore((s) => s.activePanel);
  const cursorPct = useAppStore((s) => s.cursorPct);
  const summary = useAppStore((s) => s.patientSummary);

  if (!summary) return null;

  const roscOffset = Math.max(0, summary.time_axis?.hours_rosc_to_eeg ?? 0);
  const totalHours = roscOffset + summary.qc.recording_duration_hours;
  const cursorHours = cursorPct * totalHours;
  const h = Math.floor(cursorHours);
  const m = Math.floor((cursorHours - h) * 60);
  const s = Math.floor(((cursorHours - h) * 60 - m) * 60);
  const timeStr = `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;

  const panel = PANELS.find((p) => p.panelId === activePanel);
  const panelName = activePanel === "__summary_stats__"
    ? "Summary Stats"
    : (panel?.displayName ?? activePanel);

  return { timeStr, panelName };
}

function CursorTab() {
  const readout = useCursorReadout();
  const cursorValues = useAppStore((s) => s.cursorValues);

  if (!readout) return <p className="text-xs text-muted-foreground px-1">No patient loaded.</p>;

  const entries = Object.entries(cursorValues).filter(([, v]) => v.value != null);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground uppercase tracking-widest font-mono text-[9.5px]">At cursor</span>
        <span className="font-mono bg-muted px-1.5 py-0.5 rounded text-[10px]">{readout.timeStr}</span>
      </div>
      <p className="text-[10.5px] text-muted-foreground">
        Panel: <span className="text-foreground font-medium">{readout.panelName}</span>
      </p>
      {entries.length > 0 ? (
        <div className="space-y-1">
          {entries.map(([key, entry]) => (
            <div key={key} className="flex items-center justify-between gap-2 text-[10.5px]">
              <span className="text-muted-foreground truncate">{entry.label}</span>
              <span className="font-mono text-foreground shrink-0">
                {entry.value != null ? entry.value.toFixed(3) : "—"}
                {entry.unit ? ` ${entry.unit}` : ""}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-[10.5px] text-muted-foreground">
          Drag the time axis to read values at cursor.
        </p>
      )}
    </div>
  );
}

function OverlayToggles() {
  const overlayVisibility = useAppStore((s) => s.overlayVisibility);
  const setOverlayVisibility = useAppStore((s) => s.setOverlayVisibility);

  const rows: {
    key: keyof typeof overlayVisibility;
    label: string;
    description: string;
    swatchClass: string;
  }[] = [
    {
      key: "artifacts",
      label: "Artifact regions",
      description: "Epochs that failed the artifact filter",
      swatchClass: "bg-destructive/30 border border-destructive/60",
    },
    {
      key: "gaps",
      label: "Missing data",
      description: "Recording gaps and pre-ROSC periods",
      swatchClass: "bg-muted-foreground/30 border border-muted-foreground/60",
    },
    {
      key: "binBoundaries",
      label: "Bin boundaries",
      description: "Dashed verticals at configured bin edges",
      swatchClass: "bg-transparent border-l border-dashed border-muted-foreground/60 w-0",
    },
  ];

  return (
    <div className="space-y-2">
      <Label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono">
        Chart overlays
      </Label>
      <div className="space-y-1.5 rounded border border-border bg-background/60 px-2.5 py-2">
        {rows.map((row) => (
          <div key={row.key} className="flex items-center gap-2">
            <span
              aria-hidden
              className={["inline-block w-3 h-3 rounded-sm shrink-0", row.swatchClass].join(" ")}
            />
            <div className="flex-1 min-w-0">
              <div className="text-[11px] text-foreground truncate">{row.label}</div>
              <div className="text-[9.5px] text-muted-foreground truncate">{row.description}</div>
            </div>
            <Switch
              size="sm"
              checked={overlayVisibility[row.key]}
              onCheckedChange={(checked) =>
                setOverlayVisibility({ [row.key]: Boolean(checked) })
              }
            />
          </div>
        ))}
      </div>
    </div>
  );
}


function ParamsTab() {
  const patientId = useAppStore((s) => s.patientId);
  const config = useAppStore((s) => s.config);
  const updateConfig = useAppStore((s) => s.updateConfig);
  const configDirty = useAppStore((s) => s.configDirty);
  const markConfigClean = useAppStore((s) => s.markConfigClean);
  const bumpReprocessTrigger = useAppStore((s) => s.bumpReprocessTrigger);

  const [reprocessing, setReprocessing] = useState(false);
  const [reprocessError, setReprocessError] = useState<string | null>(null);

  const thresholdConfig = {
    intensity: { min: 0, max: 30, step: 0.5, label: "Intensity (μV)" },
    detector:  { min: 0, max: 1,  step: 0.01, label: "Detector" },
    quality:   { min: 0, max: 100, step: 1,   label: "Quality (%)" },
    combined:  { min: 0, max: 30, step: 0.5,  label: "Intensity (μV)" },
    none:      { min: 0, max: 30, step: 0.5,  label: "Threshold" },
  }[config.artifactMode] ?? { min: 0, max: 30, step: 0.5, label: "Threshold" };

  async function reprocess() {
    if (!patientId) return;
    setReprocessing(true);
    setReprocessError(null);
    try {
      const reprocessConfig = {
        artifact_mode: config.artifactMode,
        artifact_intensity_threshold:
          config.artifactMode === "intensity" || config.artifactMode === "combined"
            ? config.artifactThreshold : 5.0,
        artifact_quality_threshold:
          config.artifactMode === "quality" ? config.artifactThreshold : 50.0,
        seizure_mode: config.seizureMode,
        seizure_probability_threshold: config.seizureThreshold,
        bin_edges_hours: config.binEdges,
        min_coverage_hours: config.minCoverageHours,
      };
      const { job_id } = await reprocessPatient(patientId, reprocessConfig);
      const pid = patientId;
      subscribePipelineStatus(
        job_id,
        () => {},
        async () => {
          try {
            clearPatientDataCache(pid);
            const patientData = await getPatient(pid);
            useAppStore.setState({ patientSummary: patientData });
            markConfigClean();
            bumpReprocessTrigger();
          } catch (err) {
            console.error("Failed to reload after reprocess:", err);
          } finally {
            setReprocessing(false);
          }
        },
        (errMsg) => {
          setReprocessError(errMsg);
          setReprocessing(false);
        },
      );
    } catch (err) {
      setReprocessError(err instanceof Error ? err.message : "Reprocess failed");
      setReprocessing(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Dirty banner */}
      {configDirty && (
        <div className="flex items-center justify-between gap-2 px-3 py-2 rounded bg-amber-500/10 border border-amber-500/30 text-xs text-amber-600 dark:text-amber-400">
          <span>Settings changed — reprocess to apply</span>
          <Button
            size="sm"
            className="h-6 text-xs px-2"
            onClick={reprocess}
            disabled={reprocessing || !patientId}
          >
            <RefreshCw className={["h-3 w-3 mr-1", reprocessing ? "animate-spin" : ""].join(" ")} />
            {reprocessing ? "Running…" : "Reprocess"}
          </Button>
        </div>
      )}

      {reprocessError && (
        <p className="text-xs text-destructive">{reprocessError}</p>
      )}

      {/* Artifact method */}
      <div className="space-y-1.5">
        <Label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono">
          Artifact method
        </Label>
        <Select
          value={config.artifactMode}
          onValueChange={(val) => {
            const defaults: Record<string, number> = {
              intensity: 5.0, detector: 0.5, quality: 50.0, combined: 5.0, none: 0,
            };
            updateConfig({ artifactMode: val, artifactThreshold: defaults[val] ?? 5.0 });
          }}
        >
          <SelectTrigger className="h-7 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">None</SelectItem>
            <SelectItem value="intensity">Intensity</SelectItem>
            <SelectItem value="detector">Detector</SelectItem>
            <SelectItem value="quality">Quality</SelectItem>
            <SelectItem value="combined">Combined</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Artifact threshold */}
      <div className="space-y-1.5">
        <Label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono">
          {thresholdConfig.label}: {config.artifactThreshold}
        </Label>
        <Slider
          value={[config.artifactThreshold]}
          onValueChange={(val) =>
            updateConfig({ artifactThreshold: Array.isArray(val) ? val[0] : val })
          }
          min={thresholdConfig.min}
          max={thresholdConfig.max}
          step={thresholdConfig.step}
          disabled={config.artifactMode === "none"}
        />
      </div>

      {/* Seizure exclusion */}
      <div className="space-y-1.5">
        <Label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono">
          Seizure exclusion
        </Label>
        <Select
          value={config.seizureMode}
          onValueChange={(v) => updateConfig({ seizureMode: v })}
        >
          <SelectTrigger className="h-7 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">None</SelectItem>
            <SelectItem value="detected">Exclude Detected</SelectItem>
            <SelectItem value="probability">By Probability</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Seizure threshold */}
      {config.seizureMode === "probability" && (
        <div className="space-y-1.5">
          <Label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono">
            Seizure threshold: {config.seizureThreshold}
          </Label>
          <Slider
            value={[config.seizureThreshold]}
            onValueChange={(val) =>
              updateConfig({ seizureThreshold: Array.isArray(val) ? val[0] : val })
            }
            min={0}
            max={1}
            step={0.01}
          />
        </div>
      )}

      {/* Min coverage */}
      <div className="space-y-1.5">
        <Label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono">
          Min coverage / bin: {config.minCoverageHours}h
        </Label>
        <Slider
          value={[config.minCoverageHours]}
          onValueChange={(val) =>
            updateConfig({ minCoverageHours: Array.isArray(val) ? val[0] : val })
          }
          min={0}
          max={6}
          step={0.5}
        />
      </div>

      {/* Epoch bin edges */}
      <div className="space-y-1.5">
        <Label className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono">
          Epoch bins (hours)
        </Label>
        <BinEdgesInput
          value={config.binEdges}
          onChange={(edges) => updateConfig({ binEdges: edges })}
        />
      </div>

      <OverlayToggles />

      {/* Reprocess button (always visible when patient loaded) */}
      {!configDirty && patientId && (
        <Button
          variant="outline"
          size="sm"
          className="w-full text-xs"
          onClick={reprocess}
          disabled={reprocessing}
        >
          <RefreshCw className={["h-3 w-3 mr-1.5", reprocessing ? "animate-spin" : ""].join(" ")} />
          {reprocessing ? "Reprocessing…" : "Reprocess"}
        </Button>
      )}
    </div>
  );
}

export function Inspector() {
  const [tab, setTab] = useState<Tab>("cursor");
  const [collapsed, setCollapsed] = useState(false);

  const TABS: { id: Tab; label: string }[] = [
    { id: "cursor", label: "Cursor" },
    { id: "events", label: "Events" },
    { id: "params", label: "Params" },
  ];

  if (collapsed) {
    return (
      <aside
        className="flex flex-col border-l border-border bg-muted/40 overflow-hidden"
        style={{ width: 32, flexShrink: 0 }}
      >
        <button
          onClick={() => setCollapsed(false)}
          className="flex items-center justify-center w-full h-8 hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
          title="Expand inspector"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </button>
      </aside>
    );
  }

  return (
    <aside
      className="flex flex-col border-l border-border bg-muted/40 overflow-hidden"
      style={{ width: 300, flexShrink: 0 }}
    >
      {/* Tab header */}
      <div className="flex items-center justify-between px-2 py-2 border-b border-border">
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setCollapsed(true)}
            className="text-muted-foreground hover:text-foreground transition-colors p-0.5 rounded hover:bg-muted"
            title="Collapse inspector"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
          <span className="text-xs font-semibold">Inspector</span>
        </div>
        <div className="flex rounded border border-border overflow-hidden">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={[
                "px-2 py-0.5 text-[10.5px] border-r border-border last:border-r-0 transition-colors",
                tab === t.id
                  ? "bg-foreground text-background"
                  : "bg-background text-muted-foreground hover:text-foreground",
              ].join(" ")}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content — scrollable */}
      <div className="flex-1 overflow-y-auto p-3">
        {tab === "cursor" && <CursorTab />}
        {tab === "events" && <EventList />}
        {tab === "params" && <ParamsTab />}
      </div>
    </aside>
  );
}
