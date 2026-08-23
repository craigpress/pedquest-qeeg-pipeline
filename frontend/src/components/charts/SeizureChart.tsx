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

const SEIZURE_FAMILIES = ["seizure_probability"];
const MAX_CHART_POINTS = 2000;

/** Peak-preserving downsample: within each window, keep the point with the
 *  highest seizure probability so brief spikes are never dropped. */
function downsamplePeak(
  arr: { hours: number; probability: number | null }[],
  maxPoints: number,
): typeof arr {
  if (arr.length <= maxPoints) return arr;
  const step = arr.length / maxPoints;
  const result: typeof arr = [];
  for (let i = 0; i < maxPoints; i++) {
    const start = Math.round(i * step);
    const end = Math.min(Math.round((i + 1) * step), arr.length);
    let best = start;
    for (let j = start + 1; j < end; j++) {
      if ((arr[j].probability ?? -1) > (arr[best].probability ?? -1)) {
        best = j;
      }
    }
    result.push(arr[best]);
  }
  if (result[result.length - 1] !== arr[arr.length - 1]) {
    result.push(arr[arr.length - 1]);
  }
  return result;
}

interface SeizureChartProps {
  // TODO: Pass seizure_probability_threshold from pipeline config via PatientResult.metadata
  seizureThreshold?: number;
}

export function SeizureChart({ seizureThreshold }: SeizureChartProps = {}) {
  const patientId = useAppStore((s) => s.patientId);
  const binEdges = useAppStore((s) => s.config.binEdges);
  const metadata = usePanelMetadata("seizure_probability");
  const { data, loading } = usePatientData(patientId, SEIZURE_FAMILIES);
  const { gapEnd } = usePreRecordingGap(data?.hours?.[0]);

  const chartData = useMemo(() => {
    if (!data) return [];
    const cols = Object.keys(data.columns).filter((c) => !c.startsWith("_"));
    // The continuous P14 score, not the binary detection events — both instruments
    // ship under one display label and were sharing an identifier before
    // column_schema_version 3, so match the disambiguated name explicitly and
    // never fall through to a detections column.
    const probCol = cols.find((c) => c === "seizure_probability_p14_probability")
      ?? cols.find((c) => c === "seizure_probability_p14")   // pre-v3 datasets
      ?? cols.find((c) => c.includes("prob") && c.includes("seizure")
                          && !c.includes("detection"))
      ?? cols[0];
    if (!probCol) return [];

    const full = data.hours.map((h, i) => ({
      hours: h,
      probability: data.columns[probCol]?.[i] ?? null,
    }));
    return downsamplePeak(full, MAX_CHART_POINTS);
  }, [data]);

  if (loading || chartData.length === 0) {
    return (
      <ChartContainer title="Seizure Probability" metadata={metadata}>
        <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
          {loading ? "Loading..." : "No seizure data available"}
        </div>
      </ChartContainer>
    );
  }

  return (
    <ChartContainer title="Seizure Probability" subtitle="Detection probability (0-1)" height={60} metadata={metadata}>
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
            domain={[0, 1]}
            ticks={[0, 0.25, 0.5, 0.75, 1]}
            tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            label={{
              value: "Probability",
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
          />
          <ReferenceLine
            y={seizureThreshold ?? 0.5}
            stroke="#ef4444"
            strokeDasharray="4 4"
            strokeOpacity={0.5}
            label={{ value: `Threshold (${(seizureThreshold ?? 0.5).toFixed(2)})`, position: "insideTopRight", fontSize: 9, fill: "#ef4444" }}
          />
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
            dataKey="probability"
            stroke="#ef4444"
            fill="#ef4444"
            fillOpacity={0.2}
            strokeWidth={1}
            dot={false}
            connectNulls={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
}
