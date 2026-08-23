import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
  ReferenceArea,
} from "recharts";
import { usePatientData } from "@/hooks/usePatientData";
import { usePanelMetadata } from "@/hooks/useChartMetadata";
import { usePreRecordingGap } from "@/hooks/usePreRecordingGap";
import { useAppStore } from "@/stores/appStore";
import { ChartContainer } from "./shared/ChartContainer";

const BAND_FAMILIES = ["fft_power"];
const BAND_COLORS: Record<string, string> = {
  delta: "#8b5cf6",
  theta: "#06b6d4",
  alpha: "#10b981",
  beta: "#f59e0b",
};

const MAX_CHART_POINTS = 2000;

/** Downsample an array by picking every Nth element. */
function downsample<T>(arr: T[], maxPoints: number): T[] {
  if (arr.length <= maxPoints) return arr;
  const step = arr.length / maxPoints;
  const result: T[] = [];
  for (let i = 0; i < maxPoints; i++) {
    result.push(arr[Math.round(i * step)]);
  }
  // Always include the last point
  if (result[result.length - 1] !== arr[arr.length - 1]) {
    result.push(arr[arr.length - 1]);
  }
  return result;
}

interface BandPowerChartProps {
  region: "anterior" | "posterior";
}

export function BandPowerChart({ region }: BandPowerChartProps) {
  const patientId = useAppStore((s) => s.patientId);
  const binEdges = useAppStore((s) => s.config.binEdges);
  const metadata = usePanelMetadata(`band_power_${region}`);
  const { data, loading } = usePatientData(patientId, BAND_FAMILIES);
  const { gapEnd } = usePreRecordingGap(data?.hours?.[0]);

  const { chartData, bands } = useMemo(() => {
    if (!data) return { chartData: [], bands: [] as string[] };

    // Match exactly the bilateral regional columns: fft_{band}_{region}
    // These are the averages of left+right computed by region_mapping.py.
    // Exclude per-hemisphere (left_/right_) and 2-min averaged (avg2m) variants.
    const BANDS = ["delta", "theta", "alpha", "beta"] as const;
    const bandCols: Record<string, string> = {};

    for (const band of BANDS) {
      const exactCol = `fft_${band}_${region}`;
      if (exactCol in data.columns) {
        bandCols[band] = exactCol;
      }
    }

    const bands = Object.keys(bandCols);
    const fullData = data.hours.map((h, i) => {
      const point: Record<string, number | null> = { hours: h };
      for (const [band, col] of Object.entries(bandCols)) {
        const val = data.columns[col]?.[i] ?? null;
        // Clamp near-zero/negative values to null for log scale safety
        point[band] = val !== null && val > 0 ? val : null;
      }
      return point;
    });

    const chartData = downsample(fullData, MAX_CHART_POINTS);

    return { chartData, bands };
  }, [data, region]);

  if (loading) {
    return (
      <ChartContainer title={`Band Power (${region})`} metadata={metadata}>
        <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
          Loading...
        </div>
      </ChartContainer>
    );
  }

  return (
    <ChartContainer title={`Band Power (${region})`} subtitle="Log-scale spectral power" height={150} metadata={metadata}>
      <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
        <LineChart data={chartData} syncId="qeeg-time">
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
            scale="log"
            domain={[0.01, "auto"]}
            allowDataOverflow
            tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            label={{
              value: "Power (\u00B5V\u00B2)",
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
              fontSize: 10,
            }}
            labelFormatter={(h: number) => `${h.toFixed(1)}h`}
            formatter={(value: number) => value?.toFixed(2) ?? "N/A"}
          />
          <Legend
            wrapperStyle={{ fontSize: 9 }}
            iconSize={8}
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
          {bands.map((band) => (
            <Line
              key={band}
              type="monotone"
              dataKey={band}
              stroke={BAND_COLORS[band] || "#999"}
              strokeWidth={1}
              dot={false}
              connectNulls={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
}
