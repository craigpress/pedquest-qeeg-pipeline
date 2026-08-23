import { useState, useEffect, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getBinSummary } from "@/api/client";
import { useAppStore } from "@/stores/appStore";
import type { BinSummary, BinRow } from "@/types/api";

// ── Coverage color thresholds ──────────────────────────────────────────
function coverageColor(fraction: number, thresholds: [number, number]): string {
  if (fraction >= thresholds[0]) return "text-green-600 dark:text-green-400";
  if (fraction >= thresholds[1]) return "text-yellow-600 dark:text-yellow-400";
  return "text-red-600 dark:text-red-400";
}

function coverageBg(fraction: number, thresholds: [number, number]): string {
  if (fraction >= thresholds[0]) return "bg-green-500/20 border-green-500/30";
  if (fraction >= thresholds[1]) return "bg-yellow-500/20 border-yellow-500/30";
  return "bg-red-500/20 border-red-500/30";
}

function missFlag(flag: string): { label: string; color: string } {
  switch (flag) {
    case "complete":
      return { label: "Complete", color: "text-green-600 dark:text-green-400" };
    case "MCAR":
      return { label: "MCAR", color: "text-yellow-600 dark:text-yellow-400" };
    case "MAR":
      return { label: "MAR", color: "text-orange-600 dark:text-orange-400" };
    case "MNAR":
      return { label: "MNAR", color: "text-red-600 dark:text-red-400" };
    default:
      return { label: flag || "-", color: "text-muted-foreground" };
  }
}

// ── Sparkline SVG (inline, no dependencies) ────────────────────────────
function Sparkline({
  values,
  width = 80,
  height = 20,
  color = "currentColor",
}: {
  values: (number | null)[];
  width?: number;
  height?: number;
  color?: string;
}) {
  const valid = values.filter((v): v is number => v != null && !isNaN(v));
  if (valid.length < 2) return <span className="text-[9px] text-muted-foreground">-</span>;
  const min = Math.min(...valid);
  const max = Math.max(...valid);
  const range = max - min || 1;
  const points = valid
    .map((v, i) => {
      const x = (i / (valid.length - 1)) * width;
      const y = height - ((v - min) / range) * (height - 2) - 1;
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg width={width} height={height} className="inline-block">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ── Key metric extraction helpers ──────────────────────────────────────
type MetricKey = "alpha_delta" | "theta_delta" | "total_power" | "suppression" | "seizure_burden";

const METRIC_DEFS: {
  key: MetricKey;
  label: string;
  unit: string;
  precision: number;
}[] = [
  { key: "alpha_delta", label: "ADR", unit: "", precision: 3 },
  { key: "theta_delta", label: "TDR", unit: "", precision: 3 },
  { key: "total_power", label: "Total Power", unit: "uV\u00b2", precision: 1 },
  { key: "suppression", label: "Suppression", unit: "%", precision: 1 },
  { key: "seizure_burden", label: "Seizure Burden", unit: "h", precision: 2 },
];

function findMetric(metrics: Record<string, number | null>, pattern: string, suffix: string): number | null {
  const entry = Object.entries(metrics).find(
    ([k]) => k.includes(pattern) && k.endsWith(suffix),
  );
  return entry ? entry[1] : null;
}

function findSlope(metrics: Record<string, number | null>, pattern: string): number | null {
  const entry = Object.entries(metrics).find(
    ([k]) => k.includes(pattern) && k.endsWith("_slope"),
  );
  return entry ? entry[1] : null;
}

// ── QC Timeline bar ────────────────────────────────────────────────────
function QcTimeline({
  bins,
  totalHours,
  thresholds,
}: {
  bins: BinRow[];
  totalHours: number;
  thresholds: [number, number];
}) {
  if (totalHours <= 0) return null;
  const [good, poor] = thresholds;
  return (
    <div className="space-y-1">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Recording Timeline</p>
      <div className="flex h-5 rounded overflow-hidden border border-border">
        {bins.map((b) => {
          const widthPct = ((b.bin_end_hours - b.bin_start_hours) / totalHours) * 100;
          const cf = b.coverage_fraction;
          let bg: string;
          if (cf >= good) bg = "bg-green-500";
          else if (cf >= poor) bg = "bg-yellow-500";
          else if (cf > 0) bg = "bg-red-500";
          else bg = "bg-muted";
          return (
            <div
              key={b.bin_label}
              className={`${bg} border-r border-background/50 flex items-center justify-center`}
              style={{ width: `${widthPct}%` }}
              title={`${b.bin_label}: ${(cf * 100).toFixed(0)}% coverage`}
            >
              <span className="text-[7px] text-white/80 font-mono truncate px-0.5">
                {b.bin_label}
              </span>
            </div>
          );
        })}
      </div>
      <div className="flex gap-3 text-[9px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded bg-green-500 inline-block" />
          {` Usable (>${(good * 100).toFixed(0)}%)`}
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded bg-yellow-500 inline-block" />
          {` Marginal (${(poor * 100).toFixed(0)}–${(good * 100).toFixed(0)}%)`}
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded bg-red-500 inline-block" />
          {` Low (<${(poor * 100).toFixed(0)}%)`}
        </span>
      </div>
    </div>
  );
}

interface BinStatisticsProps {
  coverageThresholds?: [number, number]; // [good, poor] defaults [0.7, 0.3]
}

// ── Main Component ─────────────────────────────────────────────────────
export function BinStatistics({ coverageThresholds = [0.7, 0.3] }: BinStatisticsProps = {}) {
  const patientId = useAppStore((s) => s.patientId);
  const [bins, setBins] = useState<BinSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [compareA, setCompareA] = useState<string | null>(null);
  const [compareB, setCompareB] = useState<string | null>(null);

  useEffect(() => {
    if (!patientId) return;
    setLoading(true);
    setCompareA(null);
    setCompareB(null);
    getBinSummary(patientId)
      .then(setBins)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [patientId]);

  // Total recording hours from the last bin edge
  const totalHours = useMemo(() => {
    if (!bins?.bin_edges.length) return 0;
    return Math.max(...bins.bin_edges);
  }, [bins]);

  // Collect sparkline data across bins
  const sparkData = useMemo(() => {
    if (!bins) return {};
    const data: Record<MetricKey, (number | null)[]> = {
      alpha_delta: [],
      theta_delta: [],
      total_power: [],
      suppression: [],
      seizure_burden: [],
    };
    for (const b of bins.bins) {
      for (const def of METRIC_DEFS) {
        if (def.key === "seizure_burden") {
          data[def.key].push(b.seizure_burden_hours);
        } else {
          data[def.key].push(findMetric(b.metrics, def.key, "_median"));
        }
      }
    }
    return data;
  }, [bins]);

  if (loading || !bins) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8 text-xs text-muted-foreground">
          {loading ? "Loading bin data..." : "No bin data"}
        </CardContent>
      </Card>
    );
  }

  const binA = compareA ? bins.bins.find((b) => b.bin_label === compareA) : null;
  const binB = compareB ? bins.bins.find((b) => b.bin_label === compareB) : null;

  return (
    <div className="space-y-4">
      {/* QC Timeline */}
      <Card>
        <CardContent className="pt-3 pb-3 px-4">
          <QcTimeline bins={bins.bins} totalHours={totalHours} thresholds={coverageThresholds} />
        </CardContent>
      </Card>

      {/* Summary Statistics Table — Features (rows) × Bins (columns) */}
      <Card>
        <CardHeader className="pb-2 pt-3 px-4">
          <CardTitle className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Summary Statistics
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-3 overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="text-left p-2 font-semibold">Feature</th>
                {bins.bins.map((b) => (
                  <th
                    key={b.bin_label}
                    className={`text-center p-2 font-semibold text-[10px] ${
                      b.coverage_fraction >= coverageThresholds[0]
                        ? "bg-muted/30"
                        : b.coverage_fraction >= coverageThresholds[1]
                          ? "bg-muted/50"
                          : "bg-muted/70"
                    }`}
                  >
                    <div>{b.bin_label}</div>
                    <div className="text-[9px] text-muted-foreground">
                      {(b.coverage_fraction * 100).toFixed(0)}%
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {/* Coverage row */}
              <tr className="border-b hover:bg-muted/20">
                <td className="p-2 font-mono text-muted-foreground">Coverage</td>
                {bins.bins.map((b) => (
                  <td
                    key={b.bin_label}
                    className="text-center p-2 font-mono text-[10px]"
                    style={{
                      backgroundColor:
                        b.coverage_fraction >= coverageThresholds[0]
                          ? "rgba(34, 197, 94, 0.1)"
                          : b.coverage_fraction >= coverageThresholds[1]
                            ? "rgba(234, 179, 8, 0.1)"
                            : "rgba(239, 68, 68, 0.1)",
                    }}
                  >
                    {b.coverage_hours.toFixed(1)}h
                  </td>
                ))}
              </tr>

              {/* BCI row (if available) */}
              {bins.bins.some((b) => b.background_continuity_index != null) && (
                <tr className="border-b hover:bg-muted/20">
                  <td className="p-2 font-mono text-muted-foreground">BCI</td>
                  {bins.bins.map((b) => (
                    <td key={b.bin_label} className="text-center p-2 font-mono text-[10px]">
                      {b.background_continuity_index?.toFixed(2) ?? "—"}
                    </td>
                  ))}
                </tr>
              )}

              {/* Key metrics rows */}
              {METRIC_DEFS.map((def) => (
                <tr key={def.key} className="border-b hover:bg-muted/20">
                  <td className="p-2 font-mono text-muted-foreground">{def.label}</td>
                  {bins.bins.map((b) => {
                    const val = def.key === "seizure_burden"
                      ? b.seizure_burden_hours
                      : findMetric(b.metrics, def.key, "_median");
                    return (
                      <td
                        key={b.bin_label}
                        className="text-center p-2 font-mono text-[10px]"
                        style={{
                          backgroundColor: !b.meets_minimum
                            ? "rgba(239, 68, 68, 0.05)"
                            : b.coverage_fraction >= coverageThresholds[0]
                              ? "transparent"
                              : "rgba(255, 193, 7, 0.1)",
                        }}
                      >
                        {val != null ? `${val.toFixed(def.precision)}${def.unit ? ` ${def.unit}` : ""}` : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[9px] text-muted-foreground mt-2 px-1">
            Values shown are medians. Clear cells = complete data, yellow tint = marginal, red tint = below minimum threshold.
          </p>
        </CardContent>
      </Card>

      {/* Sparkline trend overview */}
      <Card>
        <CardHeader className="pb-1 pt-2 px-4">
          <CardTitle className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Trend Overview (Bin Medians)
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-3">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {METRIC_DEFS.map((def) => (
              <div key={def.key} className="space-y-0.5">
                <p className="text-[10px] text-muted-foreground">{def.label}</p>
                <Sparkline
                  values={sparkData[def.key] || []}
                  color="var(--primary)"
                />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Bin Comparison */}
      {binA && binB && (
        <Card>
          <CardHeader className="pb-1 pt-2 px-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Bin Comparison: {binA.bin_label} vs {binB.bin_label}
              </CardTitle>
              <Button
                variant="ghost"
                size="sm"
                className="text-[9px] h-5"
                onClick={() => { setCompareA(null); setCompareB(null); }}
              >
                Clear
              </Button>
            </div>
          </CardHeader>
          <CardContent className="px-4 pb-3">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="text-[10px] text-muted-foreground border-b border-border">
                  <th className="text-left py-1">Metric</th>
                  <th className="text-right py-1">{binA.bin_label}</th>
                  <th className="text-right py-1">{binB.bin_label}</th>
                  <th className="text-right py-1">Diff</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-border/30">
                  <td className="py-1">Coverage</td>
                  <td className="text-right">{binA.coverage_hours.toFixed(1)}h</td>
                  <td className="text-right">{binB.coverage_hours.toFixed(1)}h</td>
                  <td className="text-right">{(binB.coverage_hours - binA.coverage_hours).toFixed(1)}h</td>
                </tr>
                {binA.background_continuity_index != null && binB.background_continuity_index != null && (
                  <tr className="border-b border-border/30">
                    <td className="py-1">BCI</td>
                    <td className="text-right">{binA.background_continuity_index.toFixed(2)}</td>
                    <td className="text-right">{binB.background_continuity_index.toFixed(2)}</td>
                    <td className="text-right">{(binB.background_continuity_index - binA.background_continuity_index).toFixed(2)}</td>
                  </tr>
                )}
                {METRIC_DEFS.map((def) => {
                  const vA = def.key === "seizure_burden"
                    ? binA.seizure_burden_hours
                    : findMetric(binA.metrics, def.key, "_median");
                  const vB = def.key === "seizure_burden"
                    ? binB.seizure_burden_hours
                    : findMetric(binB.metrics, def.key, "_median");
                  if (vA == null && vB == null) return null;
                  const diff = vA != null && vB != null ? vB - vA : null;
                  return (
                    <tr key={def.key} className="border-b border-border/30">
                      <td className="py-1">{def.label}</td>
                      <td className="text-right">{vA?.toFixed(def.precision) ?? "-"}</td>
                      <td className="text-right">{vB?.toFixed(def.precision) ?? "-"}</td>
                      <td className={`text-right ${diff != null && diff > 0 ? "text-green-600 dark:text-green-400" : diff != null && diff < 0 ? "text-red-600 dark:text-red-400" : ""}`}>
                        {diff != null ? (diff > 0 ? "+" : "") + diff.toFixed(def.precision) : "-"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
