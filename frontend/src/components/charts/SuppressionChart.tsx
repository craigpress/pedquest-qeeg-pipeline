import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from "recharts";
import { usePatientData } from "@/hooks/usePatientData";
import { usePanelMetadata } from "@/hooks/useChartMetadata";
import { usePreRecordingGap } from "@/hooks/usePreRecordingGap";
import { useAppStore } from "@/stores/appStore";
import { ChartContainer } from "./shared/ChartContainer";

interface SimpleLineChartProps {
  title: string;
  subtitle?: string;
  families: string[];
  columnFilter?: (col: string) => boolean;
  serverColumnFilter?: string;
  yDomain?: [number, number];
  color?: string;
  colors?: string[];
  colorResolver?: (col: string, idx: number) => string;
  labelMap?: Record<string, string>;
  showLegend?: boolean;
  height?: number;
  yLabel?: string;
  panelId?: string;
}

export function SimpleLineChart({
  title,
  subtitle,
  families,
  columnFilter,
  serverColumnFilter,
  yDomain,
  color = "#10b981",
  colors,
  colorResolver,
  labelMap,
  showLegend,
  height = 150,
  yLabel,
  panelId,
}: SimpleLineChartProps) {
  const patientId = useAppStore((s) => s.patientId);
  const binEdges = useAppStore((s) => s.config.binEdges);
  const metadata = usePanelMetadata(panelId);
  const { data, loading, error } = usePatientData(patientId, families, serverColumnFilter);
  const { gapEnd } = usePreRecordingGap(data?.hours?.[0]);

  const { chartData, colNames } = useMemo(() => {
    if (!data) return { chartData: [], colNames: [] };
    const cols = Object.keys(data.columns).filter((c) => !c.startsWith("_"));
    console.log(`[${title}] Columns:`, cols.length, cols.slice(0, 3));
    const matchingCols = columnFilter ? cols.filter(columnFilter) : cols;
    if (matchingCols.length === 0) return { chartData: [], colNames: [] };

    // Use first matching column if no filter, or all matching if filter provided
    const selectedCols = matchingCols.length > 0 ? matchingCols : [cols[0]];

    // Downsample BEFORE building objects — 129k reduce+spread is O(cols×epochs)
    const n = data.hours.length;
    const maxPts = 2000;
    const step = n <= maxPts ? 1 : n / maxPts;
    const count = n <= maxPts ? n : maxPts;

    const chartData: Record<string, number | null>[] = [];
    for (let j = 0; j < count; j++) {
      const i = Math.round(j * step);
      const pt: Record<string, number | null> = { hours: data.hours[i] };
      for (const col of selectedCols) {
        pt[col] = data.columns[col]?.[i] ?? null;
      }
      chartData.push(pt);
    }
    // Always include last point
    if (n > maxPts) {
      const last: Record<string, number | null> = { hours: data.hours[n - 1] };
      for (const col of selectedCols) {
        last[col] = data.columns[col]?.[n - 1] ?? null;
      }
      chartData.push(last);
    }

    return { chartData, colNames: selectedCols };
  }, [data, columnFilter]);

  if (loading || chartData.length === 0 || error) {
    return (
      <ChartContainer title={title} subtitle={subtitle} metadata={metadata}>
        <div className={`flex items-center justify-center h-full text-xs ${error ? "text-red-400" : "text-muted-foreground"}`}>
          {loading ? "Loading..." : error ? `Error: ${error}` : `No ${title.toLowerCase()} data`}
        </div>
      </ChartContainer>
    );
  }

  const getLineColor = (col: string, idx: number): string => {
    if (colorResolver) return colorResolver(col, idx);
    if (colors) return colors[idx % colors.length];
    if (colNames.length > 1) return [color, color === "#06b6d4" ? "#ec4899" : "#10b981"][idx % 2];
    return color;
  };

  const getLineLabel = (col: string): string => labelMap?.[col] ?? col;

  return (
    <ChartContainer title={title} subtitle={subtitle} height={height} metadata={metadata}>
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
            domain={yDomain || ["auto", "auto"]}
            tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            label={yLabel ? {
              value: yLabel,
              angle: -90,
              position: "insideLeft",
              style: { fontSize: 11, fill: "var(--muted-foreground)" },
            } : undefined}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--card)",
              border: "1px solid var(--border)",
              color: "var(--foreground)",
              fontSize: 11,
            }}
            labelFormatter={(h: number) => `${h.toFixed(1)}h`}
            formatter={(val: number, name: string) => [val?.toFixed(3) ?? "N/A", getLineLabel(name)]}
          />
          {showLegend && (
            <Legend
              wrapperStyle={{ fontSize: 11 }}
              formatter={(v: string) => getLineLabel(v)}
            />
          )}
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
          {colNames.map((colName, idx) => (
            <Line
              key={colName}
              type="monotone"
              dataKey={colName}
              name={colName}
              stroke={getLineColor(colName, idx)}
              strokeWidth={1}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
}
