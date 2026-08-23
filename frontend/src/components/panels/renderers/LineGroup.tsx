import { useMemo } from "react";
import { useCursorSnapshot } from "@/hooks/useCursorSnapshot";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SubChartGroup } from "@/panels/types";
import type { EpochData } from "@/types/api";
import { useAppStore } from "@/stores/appStore";
import { usePreRecordingGap } from "@/hooks/usePreRecordingGap";
import { ChartContainer } from "@/components/charts/shared/ChartContainer";
import { groupToMetadata } from "@/panels/groupMetadata";
import { ChartOverlays, CursorLine } from "./overlays";

interface LineGroupProps {
  group: SubChartGroup;
  data: EpochData | null;
}

const MAX_POINTS = 2000;

export function LineGroup({ group, data }: LineGroupProps) {
  const binEdges = useAppStore((s) => s.config.binEdges);
  const cursorPct = useAppStore((s) => s.cursorPct);
  const summary = useAppStore((s) => s.patientSummary);
  const roscOffset = Math.max(0, summary?.time_axis?.hours_rosc_to_eeg ?? 0);
  const totalHours = roscOffset + (summary?.qc.recording_duration_hours ?? 0);
  const cursorHours = cursorPct * totalHours;
  const { gapEnd } = usePreRecordingGap(data?.hours?.[0]);

  // Collect every column this group wants to plot, plus trace metadata for legend/color.
  const plan = useMemo(() => {
    type TracePlan = { dataKey: string; color: string; label: string; style: "solid" | "dashed" };
    const traces: TracePlan[] = [];
    const missing: string[] = [];
    for (const row of group.rows) {
      for (const trace of row.traces) {
        if (trace.source.kind === "column") {
          traces.push({
            dataKey: trace.source.key,
            color: trace.color,
            label: trace.label,
            style: trace.style ?? "solid",
          });
        } else if (trace.source.kind === "missing") {
          missing.push(trace.label);
        }
      }
    }
    return { traces, missing };
  }, [group]);

  const { chartData, logScale } = useMemo(() => {
    if (!data) return { chartData: [], logScale: group.rows[0]?.logScale ?? false };
    const cols = plan.traces.map((t) => t.dataKey).filter((k) => data.columns[k]);
    if (cols.length === 0) return { chartData: [], logScale: false };

    const n = data.hours.length;
    const step = n <= MAX_POINTS ? 1 : n / MAX_POINTS;
    const count = n <= MAX_POINTS ? n : MAX_POINTS;

    const out: Record<string, number | null>[] = [];
    for (let j = 0; j < count; j++) {
      const i = Math.round(j * step);
      const pt: Record<string, number | null> = { hours: data.hours[i] };
      for (const col of cols) pt[col] = data.columns[col]?.[i] ?? null;
      out.push(pt);
    }
    if (n > MAX_POINTS) {
      const i = n - 1;
      const pt: Record<string, number | null> = { hours: data.hours[i] };
      for (const col of cols) pt[col] = data.columns[col]?.[i] ?? null;
      out.push(pt);
    }
    return { chartData: out, logScale: group.rows[0]?.logScale ?? false };
  }, [data, plan, group]);

  const noData = chartData.length === 0;
  const yDomain = group.rows[0]?.yDomain;
  const thresholdY = group.rows[0]?.thresholdY;

  useCursorSnapshot(
    chartData,
    plan.traces.map((t) => ({ key: t.dataKey, label: t.label })),
  );

  return (
    <ChartContainer title={group.label} height={group.height} metadata={groupToMetadata(group)}>
      {noData ? (
        <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
          {plan.missing.length > 0
            ? `No data (${plan.missing.length} missing: ${plan.missing.join(", ")})`
            : "No data"}
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
          <LineChart data={chartData} syncId="qeeg-time" margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
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
              scale={logScale ? "log" : "auto"}
              domain={logScale ? (yDomain ?? [0.001, "auto"]) : (yDomain ?? ["auto", "auto"])}
              allowDataOverflow
              tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
              width={56}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--card)",
                border: "1px solid var(--border)",
                color: "var(--foreground)",
                fontSize: 11,
              }}
              labelFormatter={(h: number) => `${h.toFixed(1)}h`}
              formatter={(val: number, name: string) => {
                const trace = plan.traces.find((t) => t.dataKey === name);
                return [val?.toFixed(3) ?? "N/A", trace?.label ?? name];
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: 11 }}
              formatter={(v: string) => plan.traces.find((t) => t.dataKey === v)?.label ?? v}
            />
            <ChartOverlays binEdges={binEdges} gapEnd={gapEnd} />
            <CursorLine cursorHours={cursorHours} />
            {thresholdY != null && (
              <ReferenceLine
                y={thresholdY}
                ifOverflow="extendDomain"
                stroke="var(--muted-foreground)"
                strokeDasharray="4 2"
                strokeOpacity={0.6}
                label={{ value: `${thresholdY}`, position: "insideTopRight", fontSize: 9, fill: "var(--muted-foreground)" }}
              />
            )}
            {plan.traces.map((t) => (
              <Line
                key={t.dataKey}
                type="monotone"
                dataKey={t.dataKey}
                stroke={t.color}
                strokeWidth={1}
                strokeDasharray={t.style === "dashed" ? "4 2" : undefined}
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </ChartContainer>
  );
}
