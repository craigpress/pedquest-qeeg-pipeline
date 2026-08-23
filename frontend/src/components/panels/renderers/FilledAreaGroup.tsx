/**
 * Filled-area renderer for diverging asymmetry indices (REASI/EASI) and the
 * seizure-probability row. Splits a ±1 series into positive/negative halves
 * so the positive side fills red and the negative side fills blue (or uses a
 * single fill for 0-1 traces).
 */

import { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
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

export function FilledAreaGroup({ group, data }: Props) {
  const binEdges = useAppStore((s) => s.config.binEdges);
  const cursorPct = useAppStore((s) => s.cursorPct);
  const summary = useAppStore((s) => s.patientSummary);
  const roscOffset = Math.max(0, summary?.time_axis?.hours_rosc_to_eeg ?? 0);
  const cursorHours = cursorPct * (roscOffset + (summary?.qc.recording_duration_hours ?? 0));
  const { gapEnd } = usePreRecordingGap(data?.hours?.[0]);

  const { chartData, diverging, traces } = useMemo(() => {
    const yMin = group.rows[0]?.yDomain?.[0] ?? 0;
    const yMax = group.rows[0]?.yDomain?.[1] ?? 1;
    const isDiverging = yMin < 0 && yMax > 0;

    const cols = group.rows
      .flatMap((r) => r.traces.filter((t) => t.source.kind === "column"))
      .map((t) => (t.source as { kind: "column"; key: string }).key);

    if (!data) return { chartData: [], diverging: isDiverging, traces: [] };
    const availableCols = cols.filter((c) => data.columns[c]);
    if (availableCols.length === 0) return { chartData: [], diverging: isDiverging, traces: [] };

    const n = data.hours.length;
    const step = n <= MAX_POINTS ? 1 : n / MAX_POINTS;
    const count = n <= MAX_POINTS ? n : MAX_POINTS;

    const out: Record<string, number | null>[] = [];
    for (let j = 0; j < count; j++) {
      const i = Math.round(j * step);
      const pt: Record<string, number | null> = { hours: data.hours[i] };
      for (const col of availableCols) {
        const v = data.columns[col]?.[i] ?? null;
        if (isDiverging) {
          pt[`${col}_pos`] = v != null && v > 0 ? v : null;
          pt[`${col}_neg`] = v != null && v < 0 ? v : null;
        } else {
          pt[col] = v;
        }
      }
      out.push(pt);
    }

    const traceList = group.rows.flatMap((row) =>
      row.traces
        .filter((t) => t.source.kind === "column")
        .map((t) => ({
          col: (t.source as { kind: "column"; key: string }).key,
          color: t.color,
          label: t.label,
          fillOpacity: t.fillOpacity ?? (isDiverging ? 0.45 : 0.4),
        })),
    );

    return { chartData: out, diverging: isDiverging, traces: traceList };
  }, [data, group]);

  const noData = chartData.length === 0;
  const yDomain = group.rows[0]?.yDomain;

  return (
    <ChartContainer title={group.label} height={group.height} metadata={groupToMetadata(group)}>
      {noData ? (
        <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
          No data
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
          <ComposedChart data={chartData} syncId="qeeg-time" margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
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
              domain={yDomain ?? ["auto", "auto"]}
              tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
              tickCount={yDomain ? 3 : 5}
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
            {diverging && <ReferenceLine y={0} stroke="var(--muted-foreground)" strokeDasharray="2 2" />}
            {traces.map((t) =>
              diverging ? (
                <>
                  <Area
                    key={`${t.col}_pos`}
                    type="monotone"
                    dataKey={`${t.col}_pos`}
                    name={`${t.label} (R>L)`}
                    stroke="#ef4444"
                    fill="#ef4444"
                    fillOpacity={t.fillOpacity}
                    isAnimationActive={false}
                    baseValue={0}
                    connectNulls={false}
                  />
                  <Area
                    key={`${t.col}_neg`}
                    type="monotone"
                    dataKey={`${t.col}_neg`}
                    name={`${t.label} (L>R)`}
                    stroke="#3b82f6"
                    fill="#3b82f6"
                    fillOpacity={t.fillOpacity}
                    isAnimationActive={false}
                    baseValue={0}
                    connectNulls={false}
                  />
                </>
              ) : (
                <Area
                  key={t.col}
                  type="monotone"
                  dataKey={t.col}
                  name={t.label}
                  stroke={t.color}
                  fill={t.color}
                  fillOpacity={t.fillOpacity}
                  isAnimationActive={false}
                  connectNulls={false}
                />
              ),
            )}
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </ChartContainer>
  );
}
