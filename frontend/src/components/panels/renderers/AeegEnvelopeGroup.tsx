/**
 * Renders the aEEG margin band. Left (blue) and Right (red) envelopes are each
 * drawn as a filled band between their lower and upper margins at 50% opacity.
 * Where the bands overlap the SVG alpha compositing produces a visible blended
 * colour — no explicit overlap detection needed.
 *
 * Rendering uses a stacked-Area approach (transparent base + coloured fill)
 * on a linear scale. Log scale was abandoned because Recharts tuple-range
 * Areas silently drop their fill on log axes.
 */

import { useMemo } from "react";
import { useCursorSnapshot } from "@/hooks/useCursorSnapshot";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
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

interface Env {
  upperKey: string;
  lowerKey: string;
  bandKey: string;
  color: string;
  label: string;
}

const MAX_POINTS = 2000;

export function AeegEnvelopeGroup({ group, data }: Props) {
  const binEdges = useAppStore((s) => s.config.binEdges);
  const cursorPct = useAppStore((s) => s.cursorPct);
  const summary = useAppStore((s) => s.patientSummary);
  const roscOffset = Math.max(0, summary?.time_axis?.hours_rosc_to_eeg ?? 0);
  const totalHours = roscOffset + (summary?.qc.recording_duration_hours ?? 0);
  const cursorHours = cursorPct * totalHours;
  const { gapEnd } = usePreRecordingGap(data?.hours?.[0]);

  const { chartData, envelopes } = useMemo(() => {
    if (!data) return { chartData: [], envelopes: [] };

    const envs: Env[] = [];
    for (const row of group.rows) {
      const cols = row.traces
        .filter((t) => t.source.kind === "column")
        .map((t) => (t.source as { kind: "column"; key: string }).key);
      // aEEG sub-cols per CSV Format Reference §3.4: _max (upper envelope), _min (lower envelope)
      const upperKey = cols.find((c) => c.endsWith("_max"));
      const lowerKey = cols.find((c) => c.endsWith("_min"));
      if (upperKey && lowerKey && data.columns[upperKey] && data.columns[lowerKey]) {
        envs.push({
          upperKey,
          lowerKey,
          bandKey: `${row.label}__bandH`,
          color: row.traces[0]?.color ?? "#3b82f6",
          label: row.label,
        });
      }
    }
    if (envs.length === 0) return { chartData: [], envelopes: [] };

    const n = data.hours.length;
    const step = n <= MAX_POINTS ? 1 : n / MAX_POINTS;
    const count = n <= MAX_POINTS ? n : MAX_POINTS;

    const out: Record<string, number | null>[] = [];
    for (let j = 0; j < count; j++) {
      const i = Math.round(j * step);
      const pt: Record<string, number | null> = { hours: data.hours[i] };
      for (const env of envs) {
        const lo = data.columns[env.lowerKey]?.[i] ?? null;
        const up = data.columns[env.upperKey]?.[i] ?? null;
        pt[env.lowerKey] = lo;
        pt[env.bandKey] = lo != null && up != null ? up - lo : null;
      }
      out.push(pt);
    }

    return { chartData: out, envelopes: envs };
  }, [data, group]);

  const noData = chartData.length === 0;

  useCursorSnapshot(
    chartData,
    envelopes.flatMap((env) => [
      { key: env.lowerKey, label: `${env.label} lower (μV)` },
    ]),
  );

  return (
    <ChartContainer title={group.label} height={group.height} metadata={groupToMetadata(group)}>
      {noData ? (
        <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
          No aEEG data
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
              scale="auto"
              domain={[0, "dataMax"]}
              allowDataOverflow
              tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
              tickFormatter={(v: number) => `${v.toFixed(0)}`}
              label={{ value: "μV", angle: -90, position: "insideLeft", fontSize: 10, fill: "var(--muted-foreground)" }}
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
                const env = envelopes.find((e) => e.lowerKey === name || e.bandKey === name);
                if (!env) return [val?.toFixed(1) ?? "N/A", name];
                const label = name === env.lowerKey ? `${env.label} lower` : `${env.label} upper`;
                return [val?.toFixed(1) ?? "N/A", label];
              }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <ChartOverlays binEdges={binEdges} gapEnd={gapEnd} />
            <CursorLine cursorHours={cursorHours} />
            {envelopes.flatMap((env) => [
              // Transparent base lifts the coloured fill to start at the lower margin
              <Area
                key={`${env.label}__base`}
                type="monotone"
                dataKey={env.lowerKey}
                name={env.label}
                stackId={`stack_${env.label}`}
                stroke="none"
                fill="transparent"
                isAnimationActive={false}
                connectNulls={false}
                legendType="none"
              />,
              // Coloured fill from lower to upper margin
              <Area
                key={env.bandKey}
                type="monotone"
                dataKey={env.bandKey}
                name={env.label}
                stackId={`stack_${env.label}`}
                stroke={env.color}
                strokeWidth={1.5}
                fill={env.color}
                fillOpacity={0.5}
                isAnimationActive={false}
                connectNulls={false}
              />,
            ])}
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </ChartContainer>
  );
}
