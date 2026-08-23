/** Global application state using Zustand. */
import { create } from "zustand";
import type { PatientSummary, OverlayData, ChartMetadata } from "@/types/api";

export type PanelPreset = "comprehensive" | "bedside" | "research" | "minimal" | "custom";
export type ViewMode = "import" | "dashboard" | "patients" | "compare" | "export";

interface AppState {
  // Navigation
  view: ViewMode;
  setView: (v: ViewMode) => void;

  // Theme
  theme: "dark" | "light";
  toggleTheme: () => void;

  // Active patient
  patientId: string | null;
  patientSummary: PatientSummary | null;
  setPatient: (id: string | null, summary?: PatientSummary | null) => void;

  // Pipeline config
  config: {
    artifactMode: string;
    artifactThreshold: number;
    seizureMode: string;
    seizureThreshold: number;
    binEdges: number[];
    roscTime: string;
    minCoverageHours: number;
  };
  updateConfig: (partial: Partial<AppState["config"]>) => void;
  configDirty: boolean;
  markConfigClean: () => void;

  // Pipeline status
  pipelineStatus: "idle" | "running" | "complete" | "error";
  pipelineProgress: number;
  pipelineMessage: string;
  setPipelineStatus: (
    status: AppState["pipelineStatus"],
    progress?: number,
    message?: string,
  ) => void;

  // Dashboard UI
  activeTab: string;
  setActiveTab: (tab: string) => void;
  /** Active Persyst panel in the rebuilt dashboard. Persisted in localStorage. */
  activePanel: string;
  setActivePanel: (panelId: string) => void;
  panelPreset: PanelPreset;
  setPanelPreset: (preset: PanelPreset) => void;
  enabledPanels: string[];
  setEnabledPanels: (panels: string[]) => void;

  // Overlay data (cached per patient)
  overlayData: OverlayData | null;
  setOverlayData: (data: OverlayData | null) => void;

  // Per-overlay visibility toggles (persisted). Default: show everything.
  overlayVisibility: {
    artifacts: boolean;
    gaps: boolean;
    binBoundaries: boolean;
  };
  setOverlayVisibility: (
    partial: Partial<AppState["overlayVisibility"]>,
  ) => void;

  // Chart metadata (cached per patient)
  chartMetadata: ChartMetadata | null;
  setChartMetadata: (data: ChartMetadata | null) => void;

  // Reprocess signal (increment to trigger dashboard reload)
  reprocessTrigger: number;
  bumpReprocessTrigger: () => void;

  // Time sync (shared zoom domain)
  timeDomain: [number, number] | null;
  setTimeDomain: (domain: [number, number] | null) => void;

  // Workbench v2 — shared cursor (0..1 fraction of recording)
  cursorPct: number;
  setCursorPct: (pct: number) => void;

  // Values at cursor position, populated by the visible chart renderers.
  // Backed by a per-chart map so multiple charts don't clobber each other;
  // `cursorValues` is the flat merged view for read-only consumers.
  cursorValues: Record<string, { label: string; value: number | null; unit?: string }>;
  /**
   * Replace the entire flat view. Most callers should use
   * ``setCursorValuesForOwner`` so their entries merge with other charts.
   */
  setCursorValues: (values: Record<string, { label: string; value: number | null; unit?: string }>) => void;
  /** Per-chart map: owner → {entry key → CursorEntry}. */
  cursorValuesByOwner: Record<string, Record<string, { label: string; value: number | null; unit?: string }>>;
  setCursorValuesForOwner: (
    ownerId: string,
    values: Record<string, { label: string; value: number | null; unit?: string }>,
  ) => void;
  clearCursorValuesForOwner: (ownerId: string) => void;

  // Spectrogram color scale preference (per family)
  spectrogramColorScales: {
    fft: string;
    rhythmicity: string;
    asymmetry: string;
    coherence: string;
  };
  /** Back-compat: returns the FFT family scale. */
  spectrogramColorScale: string;
  setSpectrogramColorScale: (
    family: keyof AppState["spectrogramColorScales"],
    scale: string,
  ) => void;
}

export type SpectrogramFamily = "fft" | "rhythmicity" | "asymmetry" | "coherence";

const DEFAULT_SPECTROGRAM_COLOR_SCALES = {
  fft: "eeg_clinical",
  rhythmicity: "viridis",
  asymmetry: "RdBu",
  coherence: "viridis",
} as const;

const ALL_PANELS = [
  "artifact_intensity",
  "seizure_probability",
  "aeeg",
  "fft_spectrogram_left",
  "fft_spectrogram_right",
  "asymmetry_spectrogram",
  "reasi",
  "band_power_anterior",
  "band_power_posterior",
  "adr_tdr_ratios",
  "suppression_ratio",
  "spike_density",
  "rhythmicity_spectrogram",
  "coherence_spectrogram",
];

const PRESET_PANELS: Record<PanelPreset, string[]> = {
  comprehensive: ALL_PANELS,
  bedside: [
    "artifact_intensity",
    "seizure_probability",
    "aeeg",
    "suppression_ratio",
    "spike_density",
  ],
  research: [
    "fft_spectrogram_left",
    "fft_spectrogram_right",
    "band_power_anterior",
    "band_power_posterior",
    "adr_tdr_ratios",
    "asymmetry_spectrogram",
  ],
  minimal: ["aeeg", "seizure_probability"],
  custom: ALL_PANELS,
};

// Helper to safely read localStorage
function getSavedPatientId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem("activePatientId");
  } catch {
    return null;
  }
}

function getSavedTheme(): "dark" | "light" {
  if (typeof window === "undefined") return "dark";
  try {
    const saved = localStorage.getItem("theme");
    return saved === "light" || saved === "dark" ? saved : "dark";
  } catch {
    return "dark";
  }
}

function loadSpectrogramColorScales(): AppState["spectrogramColorScales"] {
  if (typeof window === "undefined") return { ...DEFAULT_SPECTROGRAM_COLOR_SCALES };
  try {
    const raw = localStorage.getItem("spectrogramColorScales");
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<AppState["spectrogramColorScales"]>;
      return { ...DEFAULT_SPECTROGRAM_COLOR_SCALES, ...parsed };
    }
    // Migrate legacy single-scale key → fft family
    const legacy = localStorage.getItem("spectrogramColorScale");
    if (legacy) {
      return { ...DEFAULT_SPECTROGRAM_COLOR_SCALES, fft: legacy };
    }
  } catch {}
  return { ...DEFAULT_SPECTROGRAM_COLOR_SCALES };
}

const DEFAULT_OVERLAY_VISIBILITY: AppState["overlayVisibility"] = {
  artifacts: true,
  gaps: true,
  binBoundaries: true,
};

function loadOverlayVisibility(): AppState["overlayVisibility"] {
  if (typeof window === "undefined") return { ...DEFAULT_OVERLAY_VISIBILITY };
  try {
    const raw = localStorage.getItem("overlayVisibility");
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<AppState["overlayVisibility"]>;
      return { ...DEFAULT_OVERLAY_VISIBILITY, ...parsed };
    }
  } catch {}
  return { ...DEFAULT_OVERLAY_VISIBILITY };
}

const loadedSpectrogramScales = loadSpectrogramColorScales();

export const useAppStore = create<AppState>((set) => ({
  // Navigation
  view: "import",
  setView: (v) => set({ view: v }),

  // Theme
  theme: getSavedTheme(),
  toggleTheme: () =>
    set((s) => {
      const next = s.theme === "dark" ? "light" : "dark";
      if (typeof window !== "undefined") {
        localStorage.setItem("theme", next);
        if (next === "dark") {
          document.documentElement.classList.add("dark");
        } else {
          document.documentElement.classList.remove("dark");
        }
      }
      return { theme: next };
    }),

  // Active patient
  patientId: getSavedPatientId(),
  patientSummary: null,
  setPatient: (id, summary) => {
    if (typeof window !== "undefined") {
      if (id) {
        localStorage.setItem("activePatientId", id);
      } else {
        localStorage.removeItem("activePatientId");
      }
    }
    set({
      patientId: id,
      patientSummary: summary ?? null,
      overlayData: null,
      chartMetadata: null,
      timeDomain: null,
      cursorPct: 0,
      cursorValues: {},
      cursorValuesByOwner: {},
    });
  },

  // Pipeline config
  config: {
    artifactMode: "quality",
    artifactThreshold: 50.0,
    seizureMode: "none",
    seizureThreshold: 0.5,
    binEdges: [0, 6, 12, 18, 24, 30, 36, 42, 48, 54, 60, 66, 72, 78, 84, 90, 96, 102, 108, 114, 120, 126, 132, 138, 144, 150, 156, 162, 168],
    roscTime: "",
    minCoverageHours: 1.0,
  },
  updateConfig: (partial) =>
    set((s) => ({ config: { ...s.config, ...partial }, configDirty: true })),
  configDirty: false,
  markConfigClean: () => set({ configDirty: false }),

  // Pipeline status
  pipelineStatus: "idle",
  pipelineProgress: 0,
  pipelineMessage: "",
  setPipelineStatus: (status, progress, message) =>
    set({
      pipelineStatus: status,
      pipelineProgress: progress ?? 0,
      pipelineMessage: message ?? "",
    }),

  // Dashboard UI
  activeTab: "comprehensive",
  setActiveTab: (tab) => set({ activeTab: tab }),
  activePanel: (() => {
    if (typeof window === "undefined") return "comprehensive";
    try {
      return localStorage.getItem("activePanel") || "comprehensive";
    } catch {
      return "comprehensive";
    }
  })(),
  setActivePanel: (panelId) => {
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("activePanel", panelId);
      } catch {}
    }
    set({ activePanel: panelId });
  },
  panelPreset: "comprehensive",
  setPanelPreset: (preset) =>
    set({
      panelPreset: preset,
      enabledPanels: PRESET_PANELS[preset],
    }),
  enabledPanels: ALL_PANELS,
  setEnabledPanels: (panels) => set({ enabledPanels: panels }),

  // Overlay data
  overlayData: null,
  setOverlayData: (data) => set({ overlayData: data }),

  // Per-overlay visibility toggles
  overlayVisibility: loadOverlayVisibility(),
  setOverlayVisibility: (partial) =>
    set((s) => {
      const next = { ...s.overlayVisibility, ...partial };
      if (typeof window !== "undefined") {
        try {
          localStorage.setItem("overlayVisibility", JSON.stringify(next));
        } catch {}
      }
      return { overlayVisibility: next };
    }),

  // Chart metadata
  chartMetadata: null,
  setChartMetadata: (data) => set({ chartMetadata: data }),

  // Reprocess signal
  reprocessTrigger: 0,
  bumpReprocessTrigger: () => set((s) => ({ reprocessTrigger: s.reprocessTrigger + 1 })),

  // Time sync
  timeDomain: null,
  setTimeDomain: (domain) => set({ timeDomain: domain }),

  // Workbench v2 cursor
  cursorPct: 0,
  setCursorPct: (pct) => set({ cursorPct: Math.max(0, Math.min(1, pct)) }),
  cursorValues: {},
  setCursorValues: (values) => set({ cursorValues: values, cursorValuesByOwner: { __flat: values } }),
  cursorValuesByOwner: {},
  setCursorValuesForOwner: (ownerId, values) =>
    set((s) => {
      const nextByOwner = { ...s.cursorValuesByOwner, [ownerId]: values };
      const flat: typeof s.cursorValues = {};
      for (const owner of Object.keys(nextByOwner)) {
        Object.assign(flat, nextByOwner[owner]);
      }
      return { cursorValuesByOwner: nextByOwner, cursorValues: flat };
    }),
  clearCursorValuesForOwner: (ownerId) =>
    set((s) => {
      if (!(ownerId in s.cursorValuesByOwner)) return {};
      const { [ownerId]: _dropped, ...rest } = s.cursorValuesByOwner;
      void _dropped;
      const flat: typeof s.cursorValues = {};
      for (const owner of Object.keys(rest)) {
        Object.assign(flat, rest[owner]);
      }
      return { cursorValuesByOwner: rest, cursorValues: flat };
    }),

  // Spectrogram color scales (per-family)
  spectrogramColorScales: loadedSpectrogramScales,
  // Back-compat mirror of the fft family value, kept in sync by the setter.
  spectrogramColorScale: loadedSpectrogramScales.fft,
  setSpectrogramColorScale: (family, scale) => {
    set((s) => {
      const next = { ...s.spectrogramColorScales, [family]: scale };
      if (typeof window !== "undefined") {
        try { localStorage.setItem("spectrogramColorScales", JSON.stringify(next)); } catch {}
      }
      return {
        spectrogramColorScales: next,
        spectrogramColorScale: next.fft,
      };
    });
  },
}));

export { ALL_PANELS, PRESET_PANELS };
