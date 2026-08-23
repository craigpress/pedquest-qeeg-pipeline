/**
 * Short 0/1 strip for derived boolean events (spike left-only, bilateral, etc.).
 * Each row occupies its own horizontal band [ri, ri+1]. A faint background band
 * is always rendered so inactive rows are still visible; active bins add a filled
 * tick on top using the row color at normal opacity.
 *
 * Row stacking trick: for each row ri, we stack three bars on the same stackId:
 *   1) transparent offset (height = ri) — pushes content up to the row's band
 *   2) faint always-on background (height = 1) — row backdrop
 *   3) active tick (height = 0 or 1) — filled when the derived event fires
 * This guarantees every row is visible even when all values are 0.
 */

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
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
import { DERIVED_FUNCTIONS } from "@/panels/derivations";
import { groupToMetadata } from "@/panels/groupMetadata";
import { ChartOverlays } from "./overlays";

interface Props {
  group: SubChartGroup;
  data: EpochData | null;
}

const MAX_POINTS = 4000;
const ROW_HEIGHT = 1;
const BAND_OPACITY = 0.08;
const ACTIVE_OPACITY = 0.7;

export function BooleanStripGroup({ group, data }: Props) {
  const binEdges = useAppStore((s) => s.config.binEdges);
  const { gapEnd } = usePreRecordingGap(data?.hours?.[0]);

  const { chartData, traces, missing, rowCount } = useMemo(() => {
    type T = {
      bandOffsetKey: string;
      activeOffsetKey: string;
      bandKey: string;
      activeKey: string;
      color: string;
      label: string;
      rowIndex: number;
    };
    const ts: T[] = [];
    const miss: string[] = [];
    if (!data) {
      return { chartData: [], traces: [], missing: [], rowCount: 0 };
    }

    const rCount = group.rows.length;
    const activeValues: Record<string, (number | null)[]> = {};
    for (let ri = 0; ri < rCount; ri++) {
      const row = group.rows[ri];
      for (const trace of row.traces) {
        if (trace.source.kind === "derived") {
          const fn = DERIVED_FUNCTIONS[trace.source.fn];
          const series = fn(data);
          const bandOffsetKey = `row_${ri}_${trace.source.fn}_boff`;
          const activeOffsetKey = `row_${ri}_${trace.source.fn}_aoff`;
          const bandKey = `row_${ri}_${trace.source.fn}_band`;
          const activeKey = `row_${ri}_${trace.source.fn}_active`;
          activeValues[activeKey] = series.values.map((v) =>
            v == null ? null : v === 1 ? 1 : 0,
          );
          ts.push({
            bandOffsetKey,
            activeOffsetKey,
            bandKey,
            activeKey,
            color: trace.color,
            label: trace.label,
            rowIndex: ri,
          });
        } else if (trace.source.kind === "missing") {
          miss.push(trace.label);
        }
      }
    }
    if (ts.length === 0) {
      return { chartData: [], traces: [], missing: miss, rowCount: rCount };
    }

    const n = data.hours.length;
    const step = n <= MAX_POINTS ? 1 : n / MAX_POINTS;
    const count = n <= MAX_POINTS ? n : MAX_POINTS;

    const out: Record<string, number | null>[] = [];
    for (let j = 0; j < count; j++) {
      const i = Math.round(j * step);
      const pt: Record<string, number | null> = { hours: data.hours[i] };
      for (const t of ts) {
        const v = activeValues[t.activeKey]?.[i];
        // Transparent offsets raise each stack's baseline to y=rowIndex.
        pt[t.bandOffsetKey] = t.rowIndex;
        pt[t.activeOffsetKey] = t.rowIndex;
        // Faint always-visible band occupies the full row height.
        pt[t.bandKey] = ROW_HEIGHT;
        // Active tick fills the row when the derived event fires (v === 1).
        pt[t.activeKey] = v == null ? 0 : v === 1 ? ROW_HEIGHT : 0;
      }
      out.push(pt);
    }
    return { chartData: out, traces: ts, missing: miss, rowCount: rCount };
  }, [data, group]);

  const renderedRowCount = traces.length > 0 ? Math.max(...traces.map((t) => t.rowIndex)) + 1 : 0;
  const totalHeight = Math.max(group.height, Math.max(renderedRowCount, 1) * 28);
  const noData = chartData.length === 0;

  const rowLabelByIndex = new Map<number, string>();
  for (const t of traces) {
    if (!rowLabelByIndex.has(t.rowIndex)) {
      rowLabelByIndex.set(t.rowIndex, t.label);
    }
  }
  const yTicks = Array.from({ length: renderedRowCount }, (_, i) => i + ROW_HEIGHT / 2);

  return (
    <ChartContainer title={group.label} height={totalHeight} metadata={groupToMetadata(group)}>
      {noData ? (
        <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
          {missing.length > 0 ? `Missing: ${missing.join(", ")}` : "No data"}
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
          <BarChart
            data={chartData}
            syncId="qeeg-time"
            stackOffset="none"
            margin={{ top: 5, right: 5, bottom: 5, left: 5 }}
          >
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
              type="number"
              domain={[0, Math.max(renderedRowCount, 1)]}
              ticks={yTicks}
              tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
              tickFormatter={(v: number) => {
                const label = rowLabelByIndex.get(Math.floor(v)) ?? "";
                // Strip "Spikes — " / "Spikes - " prefix so labels fit
                return label.replace(/^[^—–-]*[—–-]\s*/u, "");
              }}
              width={56}
              interval={0}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--card)",
                border: "1px solid var(--border)",
                color: "var(--foreground)",
                fontSize: 11,
              }}
              labelFormatter={(h: number) => `${h.toFixed(1)}h`}
              formatter={(value: number | string, name: string) => {
                // Suppress offset/band entries; only report active-state rows.
                if (typeof name === "string") {
                  if (name.endsWith(" (offset)") || name.endsWith(" (band)")) {
                    return [null, null] as unknown as [string, string];
                  }
                }
                return [value === 1 ? "on" : "off", name];
              }}
            />
            <ChartOverlays binEdges={binEdges} gapEnd={gapEnd} />
            {/* Two independent stacks per row:
                band stack  = [offset=ri (transparent), band=1 (faint)]         → always visible
                active stack = [offset=ri (transparent), active=0|1 (opaque)]   → only visible when on
                Render band stack first so active ticks paint on top. */}
            {traces.map((t) => (
              <Bar
                key={t.bandOffsetKey}
                dataKey={t.bandOffsetKey}
                name={`${t.label} (offset)`}
                stackId={`row-${t.rowIndex}-band`}
                fill="transparent"
                isAnimationActive={false}
                legendType="none"
              />
            ))}
            {traces.map((t) => (
              <Bar
                key={t.bandKey}
                dataKey={t.bandKey}
                name={`${t.label} (band)`}
                stackId={`row-${t.rowIndex}-band`}
                fill={t.color}
                fillOpacity={BAND_OPACITY}
                isAnimationActive={false}
                legendType="none"
              />
            ))}
            {traces.map((t) => (
              <Bar
                key={t.activeOffsetKey}
                dataKey={t.activeOffsetKey}
                name={`${t.label} (offset)`}
                stackId={`row-${t.rowIndex}-active`}
                fill="transparent"
                isAnimationActive={false}
                legendType="none"
              />
            ))}
            {traces.map((t) => (
              <Bar
                key={t.activeKey}
                dataKey={t.activeKey}
                name={t.label}
                stackId={`row-${t.rowIndex}-active`}
                fill={t.color}
                fillOpacity={ACTIVE_OPACITY}
                isAnimationActive={false}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      )}
    </ChartContainer>
  );
}
