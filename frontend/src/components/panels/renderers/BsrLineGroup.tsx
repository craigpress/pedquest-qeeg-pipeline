/** 0–1 filled line — BSR traces. Multiple traces (e.g. Left + Right) render on one chart. */

import { useMemo } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
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

interface Props {
  group: SubChartGroup;
  data: EpochData | null;
}

const MAX_POINTS = 2000;

export function BsrLineGroup({ group, data }: Props) {
  const binEdges = useAppStore((s) => s.config.binEdges);
  const cursorPct = useAppStore((s) => s.cursorPct);
  const summary = useAppStore((s) => s.patientSummary);
  const roscOffset = Math.max(0, summary?.time_axis?.hours_rosc_to_eeg ?? 0);
  const cursorHours = cursorPct * (roscOffset + (summary?.qc.recording_duration_hours ?? 0));
  const { gapEnd } = usePreRecordingGap(data?.hours?.[0]);

  const { chartData, traces } = useMemo(() => {
    type T = { col: string; color: string; label: string };
    const ts: T[] = [];
    for (const row of group.rows) {
      for (const trace of row.traces) {
        if (trace.source.kind === "column") {
          ts.push({ col: trace.source.key, color: trace.color, label: trace.label });
        }
      }
    }
    if (!data) return { chartData: [], traces: [] };
    const avail = ts.filter((t) => data.columns[t.col]);
    if (avail.length === 0) return { chartData: [], traces: [] };

    const n = data.hours.length;
    const step = n <= MAX_POINTS ? 1 : n / MAX_POINTS;
    const count = n <= MAX_POINTS ? n : MAX_POINTS;

    const out: Record<string, number | null>[] = [];
    for (let j = 0; j < count; j++) {
      const i = Math.round(j * step);
      const pt: Record<string, number | null> = { hours: data.hours[i] };
      for (const t of avail) pt[t.col] = data.columns[t.col]?.[i] ?? null;
      out.push(pt);
    }
    return { chartData: out, traces: avail };
  }, [data, group]);

  const noData = chartData.length === 0;

  return (
    <ChartContainer title={group.label} height={group.height} metadata={groupToMetadata(group)}>
      {noData ? (
        <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
          No data
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
              domain={[0, 1]}
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
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <ChartOverlays binEdges={binEdges} gapEnd={gapEnd} />
            <CursorLine cursorHours={cursorHours} />
            {traces.map((t) => (
              <Line
                key={t.col}
                type="monotone"
                dataKey={t.col}
                name={t.label}
                stroke={t.color}
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
                connectNulls={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </ChartContainer>
  );
}
