import { useMemo } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from "recharts";
import { usePatientData } from "@/hooks/usePatientData";
import { useAppStore } from "@/stores/appStore";
import { ChartContainer } from "./shared/ChartContainer";

const AEEG_FAMILIES = ["aeeg"];
const REF_LINES_Y = [5, 10, 25, 50];

export function AeegChart() {
  const patientId = useAppStore((s) => s.patientId);
  const binEdges = useAppStore((s) => s.config.binEdges);
  const { data, loading, error } = usePatientData(patientId, AEEG_FAMILIES);

  const chartData = useMemo(() => {
    if (!data) {
      console.log("[aEEG] No data object. loading:", loading, "error:", error);
      return [];
    }

    const cols = Object.keys(data.columns);
    console.log("[aEEG] Columns received:", cols.length, cols.slice(0, 5));

    // aEEG sub-cols per PersystTrendCSV_Format_Reference.md §3.4:
    //   _1=max (upper envelope), _2=min (lower envelope), _3=p50, _4=p75, _5=p25
    // Backend slugs: aeeg_{left|right}_{max,min,p50,p75,p25}
    const lUpper = cols.find((c) => c.includes("left") && c.endsWith("_max"));
    const lLower = cols.find((c) => c.includes("left") && c.endsWith("_min"));
    const rUpper = cols.find((c) => c.includes("right") && c.endsWith("_max"));
    const rLower = cols.find((c) => c.includes("right") && c.endsWith("_min"));

    console.log("[aEEG] Found: lUpper=", lUpper, "lLower=", lLower, "rUpper=", rUpper, "rLower=", rLower);

    // Fallback: any aeeg_*_max / aeeg_*_min
    const upperCol = lUpper || cols.find((c) => c.startsWith("aeeg") && c.endsWith("_max"));
    const lowerCol = lLower || cols.find((c) => c.startsWith("aeeg") && c.endsWith("_min"));

    if (!upperCol && !rUpper) {
      console.log("[aEEG] No upper columns found, returning empty");
      return [];
    }

    return data.hours.map((h, i) => {
      // Null-preserve missing/zero values so connectNulls={false} correctly breaks
      // the line at artifact/gap regions rather than clamping to 1 µV.
      const toVal = (v: number | null | undefined): number | null =>
        v != null && v > 0 ? v : null;

      const point: Record<string, number | null> = { hours: h };
      if (lUpper) point.lUpper = toVal(data.columns[lUpper]?.[i]);
      if (lLower) point.lLower = toVal(data.columns[lLower]?.[i]);
      if (rUpper) point.rUpper = toVal(data.columns[rUpper]?.[i]);
      if (rLower) point.rLower = toVal(data.columns[rLower]?.[i]);
      // Fallback single-hemisphere
      if (!lUpper && upperCol) point.lUpper = toVal(data.columns[upperCol]?.[i]);
      if (!lLower && lowerCol) point.lLower = toVal(data.columns[lowerCol]?.[i]);
      return point;
    });
  }, [data]);

  // Downsample for Recharts SVG performance
  const displayData = useMemo(() => {
    if (chartData.length <= 2000) return chartData;
    const step = Math.ceil(chartData.length / 2000);
    return chartData.filter((_, i) => i % step === 0);
  }, [chartData]);

  if (loading) {
    return (
      <ChartContainer title="aEEG" subtitle="Amplitude-Integrated EEG">
        <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
          Loading...
        </div>
      </ChartContainer>
    );
  }

  if (error) {
    return (
      <ChartContainer title="aEEG" subtitle="Amplitude-Integrated EEG">
        <div className="flex items-center justify-center h-full text-xs text-red-400">
          Error loading aEEG: {error}
        </div>
      </ChartContainer>
    );
  }

  if (chartData.length === 0) {
    return (
      <ChartContainer title="aEEG" subtitle="Amplitude-Integrated EEG">
        <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
          No aEEG data available (columns: {data ? Object.keys(data.columns).length : "no data"})
        </div>
      </ChartContainer>
    );
  }

  const hasLeft = displayData.some((d) => d.lUpper != null);
  const hasRight = displayData.some((d) => d.rUpper != null);

  return (
    <ChartContainer title="aEEG" subtitle="Amplitude-Integrated EEG (log scale)" height={180}>
      <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
        <AreaChart data={displayData} syncId="qeeg-time">
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="hours"
            type="number"
            domain={["dataMin", "dataMax"]}
            tickCount={10}
            tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            tickFormatter={(v: number) => `${v.toFixed(0)}h`}
          />
          <YAxis
            scale="log"
            domain={[1, 100]}
            ticks={[1, 2, 5, 10, 25, 50, 100]}
            tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            tickFormatter={(v: number) => `${v}`}
            label={{
              value: "\u00B5V",
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
            formatter={(val: number, name: string) => {
              const label = name === "lUpper" ? "L Upper" : name === "lLower" ? "L Lower"
                : name === "rUpper" ? "R Upper" : "R Lower";
              return [`${val?.toFixed(1)} \u00B5V`, label];
            }}
            labelFormatter={(h: number) => `${h.toFixed(1)}h`}
          />
          <Legend
            wrapperStyle={{ fontSize: 10 }}
            formatter={(value: string) =>
              value === "lUpper" ? "L Upper" : value === "lLower" ? "L Lower"
                : value === "rUpper" ? "R Upper" : "R Lower"
            }
          />
          {REF_LINES_Y.map((v) => (
            <ReferenceLine
              key={`y-${v}`}
              y={v}
              stroke="var(--muted-foreground)"
              strokeDasharray="2 4"
              strokeOpacity={0.3}
            />
          ))}
          {binEdges.slice(1, -1).map((edge) => (
            <ReferenceLine
              key={`bin-${edge}`}
              x={edge}
              stroke="var(--muted-foreground)"
              strokeDasharray="2 4"
              strokeOpacity={0.3}
            />
          ))}
          {hasLeft && (
            <>
              <Area
                type="monotone"
                dataKey="lUpper"
                stroke="#3b82f6"
                fill="transparent"
                strokeWidth={1.5}
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
              <Area
                type="monotone"
                dataKey="lLower"
                stroke="#3b82f6"
                fill="transparent"
                strokeWidth={1}
                strokeDasharray="3 3"
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            </>
          )}
          {hasRight && (
            <>
              <Area
                type="monotone"
                dataKey="rUpper"
                stroke="#ef4444"
                fill="transparent"
                strokeWidth={1.5}
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
              <Area
                type="monotone"
                dataKey="rLower"
                stroke="#ef4444"
                fill="transparent"
                strokeWidth={1}
                strokeDasharray="3 3"
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            </>
          )}
        </AreaChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
}
