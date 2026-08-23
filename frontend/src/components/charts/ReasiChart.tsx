import { useMemo } from "react";
import {
  ComposedChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from "recharts";
import { usePatientData } from "@/hooks/usePatientData";
import { usePanelMetadata } from "@/hooks/useChartMetadata";
import { usePreRecordingGap } from "@/hooks/usePreRecordingGap";
import { useAppStore } from "@/stores/appStore";
import { ChartContainer } from "./shared/ChartContainer";

const REASI_FAMILIES = ["asymmetry"];
const MAX_CHART_POINTS = 2000;
const BANDS = ["delta", "theta", "alpha", "beta", "gamma"];

export function ReasiChart() {
  const patientId = useAppStore((s) => s.patientId);
  const binEdges = useAppStore((s) => s.config.binEdges);
  const metadata = usePanelMetadata("reasi");
  const { data, loading } = usePatientData(patientId, REASI_FAMILIES, "easi");
  const { gapEnd } = usePreRecordingGap(data?.hours?.[0]);

  const { chartData, hasData } = useMemo(() => {
    if (!data) return { chartData: [], hasData: false };
    const cols = Object.keys(data.columns).filter((c) => !c.startsWith("_"));
    // Prefer REASI delta-band hemisphere (0-5 Hz, most sensitive for background laterality).
    // Fallback chain: any broadband REASI hemisphere → any REASI hemisphere → any asymmetry hemisphere.
    // Exclude EASI (absolute asymmetry, always ≥0 — wrong for ±1 display).
    const reasCol = cols.find((c) => c === "asymmetry_reasi_delta_hemisphere")
      ?? cols.find((c) => c.includes("reasi") && c.includes("hemi") && c.includes("delta"))
      ?? cols.find((c) => c.includes("reasi") && c.includes("hemi"))
      ?? cols.find((c) => c.includes("hemi") && !c.includes("easi"));
    if (!reasCol) return { chartData: [], hasData: false };

    const n = data.hours.length;
    const step = n <= MAX_CHART_POINTS ? 1 : n / MAX_CHART_POINTS;
    const count = Math.min(n, MAX_CHART_POINTS);

    const result = [];
    for (let j = 0; j < count; j++) {
      const i = Math.round(j * step);
      const val = data.columns[reasCol]?.[i] ?? null;
      result.push({
        hours: data.hours[i],
        pos: val !== null ? Math.max(val, 0) : null,
        neg: val !== null ? Math.min(val, 0) : null,
      });
    }
    if (n > MAX_CHART_POINTS) {
      const val = data.columns[reasCol]?.[n - 1] ?? null;
      result.push({
        hours: data.hours[n - 1],
        pos: val !== null ? Math.max(val, 0) : null,
        neg: val !== null ? Math.min(val, 0) : null,
      });
    }
    return { chartData: result, hasData: true };
  }, [data]);

  if (loading || !hasData) {
    return (
      <ChartContainer title="REASI — Hemisphere" metadata={metadata}>
        <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
          {loading ? "Loading..." : "No REASI data available"}
        </div>
      </ChartContainer>
    );
  }

  return (
    <ChartContainer
      title="REASI — Hemisphere"
      subtitle="Red: right > left  ·  Blue: left > right"
      height={100}
      metadata={metadata}
    >
      <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
        <ComposedChart data={chartData} syncId="qeeg-time">
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="hours"
            type="number"
            domain={[0, "dataMax"]}
            tickCount={10}
            tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            tickFormatter={(v: number) => `${v.toFixed(0)}h`}
          />
          <YAxis
            domain={[-1, 1]}
            ticks={[-1, -0.5, 0, 0.5, 1]}
            tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            label={{
              value: "REASI",
              angle: -90,
              position: "insideLeft",
              style: { fontSize: 11, fill: "var(--muted-foreground)" },
            }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--card)",
              border: "1px solid var(--border)",
              color: "var(--foreground)",
              fontSize: 11,
            }}
            labelFormatter={(h: number) => `${h.toFixed(1)}h`}
            formatter={(val: number, name: string) => [
              val?.toFixed(3),
              name === "pos" ? "R > L asymmetry" : "L > R asymmetry",
            ]}
          />
          <ReferenceLine y={0} stroke="var(--muted-foreground)" strokeWidth={1} />
          {gapEnd != null && (
            <ReferenceArea
              x1={0}
              x2={gapEnd}
              fill="var(--muted-foreground)"
              fillOpacity={0.15}
              label={{ value: "No EEG data", position: "insideTop", fontSize: 9, fill: "var(--muted-foreground)" }}
            />
          )}
          {binEdges.slice(1, -1).map((edge) => (
            <ReferenceLine
              key={`bin-${edge}`}
              x={edge}
              stroke="var(--muted-foreground)"
              strokeDasharray="2 4"
              strokeOpacity={0.3}
            />
          ))}
          <Area
            type="monotone"
            dataKey="pos"
            name="pos"
            stroke="#ef4444"
            fill="#ef4444"
            fillOpacity={0.35}
            strokeWidth={0.5}
            baseValue={0}
            dot={false}
            connectNulls={false}
            isAnimationActive={false}
            legendType="none"
          />
          <Area
            type="monotone"
            dataKey="neg"
            name="neg"
            stroke="#3b82f6"
            fill="#3b82f6"
            fillOpacity={0.35}
            strokeWidth={0.5}
            baseValue={0}
            dot={false}
            connectNulls={false}
            isAnimationActive={false}
            legendType="none"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
}
