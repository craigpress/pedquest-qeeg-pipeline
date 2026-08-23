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
import type { ChartPanelMetadata } from "@/types/api";

// ADR from fft_power_ratio (Persyst, per-hemisphere/region).
// TDR from fft_power (bilateral derived columns only).
const FAMILIES = ["fft_power_ratio", "fft_power"];

// ADR Left=Blue, ADR Right=Red, TDR=Teal (bilateral)
const C = {
  adr_left:  "#3b82f6",
  adr_right: "#ef4444",
  tdr:       "#06b6d4",
};

const LABELS: Record<string, string> = {
  adr_left:  "ADR Left",
  adr_right: "ADR Right",
  tdr:       "TDR (bilateral)",
};

type ChartRow = Record<string, number | null>;

interface RegionChartProps {
  title: string;
  subtitle: string;
  chartData: ChartRow[];
  hasAdrLeft: boolean;
  hasAdrRight: boolean;
  hasTdr: boolean;
  binEdges: number[];
  gapEnd: number | null;
  metadata: ChartPanelMetadata | null | undefined;
}

function RegionChart({ title, subtitle, chartData, hasAdrLeft, hasAdrRight, hasTdr, binEdges, gapEnd, metadata }: RegionChartProps) {
  const hasAny = hasAdrLeft || hasAdrRight || hasTdr;
  if (!hasAny || chartData.length === 0) {
    return (
      <ChartContainer title={title} subtitle={subtitle} metadata={metadata}>
        <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
          No data available
        </div>
      </ChartContainer>
    );
  }

  return (
    <ChartContainer title={title} subtitle={subtitle} height={130} metadata={metadata}>
      <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
        <LineChart data={chartData} syncId="qeeg-time">
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="hours"
            type="number"
            domain={[0, "dataMax"]}
            tickCount={10}
            tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
            tickFormatter={(v: number) => `${v.toFixed(0)}h`}
          />
          <YAxis
            tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
            domain={[0, "auto"]}
            label={{
              value: "Ratio",
              angle: -90,
              position: "insideLeft",
              style: { fontSize: 12, fill: "var(--muted-foreground)" },
            }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--card)",
              border: "1px solid var(--border)",
              color: "var(--foreground)",
              fontSize: 12,
            }}
            formatter={(val: number, name: string) => [val?.toFixed(3), LABELS[name] || name]}
            labelFormatter={(h: number) => `${h.toFixed(1)}h`}
          />
          <Legend
            wrapperStyle={{ fontSize: 12 }}
            formatter={(v: string) => LABELS[v] || v}
          />
          {gapEnd != null && (
            <ReferenceArea
              x1={0} x2={gapEnd}
              fill="var(--muted-foreground)" fillOpacity={0.15}
              label={{ value: "No EEG data", position: "insideTop", fontSize: 9, fill: "var(--muted-foreground)" }}
            />
          )}
          {binEdges.slice(1, -1).map((edge) => (
            <ReferenceLine
              key={`bin-${edge}`} x={edge}
              stroke="var(--muted-foreground)" strokeDasharray="2 4" strokeOpacity={0.3}
            />
          ))}
          {hasAdrLeft && (
            <Line type="monotone" dataKey="adr_left" name="adr_left"
              stroke={C.adr_left} strokeWidth={1.5} dot={false} connectNulls={false} isAnimationActive={false} />
          )}
          {hasAdrRight && (
            <Line type="monotone" dataKey="adr_right" name="adr_right"
              stroke={C.adr_right} strokeWidth={1.5} dot={false} connectNulls={false} isAnimationActive={false} />
          )}
          {hasTdr && (
            <Line type="monotone" dataKey="tdr" name="tdr"
              stroke={C.tdr} strokeWidth={1.5} strokeDasharray="5 3" dot={false} connectNulls={false} isAnimationActive={false} />
          )}
        </LineChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
}

export function RatioChart() {
  const patientId = useAppStore((s) => s.patientId);
  const binEdges = useAppStore((s) => s.config.binEdges);
  const metaHemi = usePanelMetadata("adr_hemisphere");
  const metaAnt  = usePanelMetadata("adr_tdr_anterior");
  const metaPost = usePanelMetadata("adr_tdr_posterior");
  const { data, loading } = usePatientData(patientId, FAMILIES);
  const { gapEnd } = usePreRecordingGap(data?.hours?.[0]);

  const { hemi, ant, post } = useMemo(() => {
    const empty = { chartData: [] as ChartRow[], hasAdrLeft: false, hasAdrRight: false, hasTdr: false };
    if (!data) return { hemi: empty, ant: empty, post: empty };

    const cols = Object.keys(data.columns);

    // Only accept exactly-named regional columns — exclude electrode-chain variants
    const col = (name: string) => cols.includes(name) ? name : undefined;

    const adrLH = col("adr_left_hemisphere");
    const adrRH = col("adr_right_hemisphere");
    const adrLA = col("adr_left_anterior");
    const adrRA = col("adr_right_anterior");
    const adrLP = col("adr_left_posterior");
    const adrRP = col("adr_right_posterior");
    const tdrA  = col("theta_delta_ratio_anterior");
    const tdrP  = col("theta_delta_ratio_posterior");

    const n = data.hours.length;
    const maxPts = 2000;
    const step = n <= maxPts ? 1 : n / maxPts;
    const count = Math.min(n, maxPts);

    function build(
      adrL: string | undefined,
      adrR: string | undefined,
      tdr:  string | undefined,
    ) {
      const series: ChartRow[] = [];
      for (let j = 0; j < count; j++) {
        const i = Math.round(j * step);
        series.push({
          hours:     data!.hours[i],
          adr_left:  adrL ? (data!.columns[adrL]?.[i] ?? null) : null,
          adr_right: adrR ? (data!.columns[adrR]?.[i] ?? null) : null,
          tdr:       tdr  ? (data!.columns[tdr]?.[i]  ?? null) : null,
        });
      }
      if (n > maxPts) {
        series.push({
          hours:     data!.hours[n - 1],
          adr_left:  adrL ? (data!.columns[adrL]?.[n - 1] ?? null) : null,
          adr_right: adrR ? (data!.columns[adrR]?.[n - 1] ?? null) : null,
          tdr:       tdr  ? (data!.columns[tdr]?.[n - 1]  ?? null) : null,
        });
      }
      return {
        chartData:   series,
        hasAdrLeft:  !!adrL,
        hasAdrRight: !!adrR,
        hasTdr:      !!tdr,
      };
    }

    return {
      hemi: build(adrLH, adrRH, undefined),
      ant:  build(adrLA, adrRA, tdrA),
      post: build(adrLP, adrRP, tdrP),
    };
  }, [data]);

  if (loading) {
    return (
      <ChartContainer title="ADR — Hemisphere" metadata={metaHemi}>
        <div className="flex items-center justify-center h-full text-xs text-muted-foreground">Loading...</div>
      </ChartContainer>
    );
  }

  return (
    <>
      <RegionChart
        title="ADR — Hemisphere"
        subtitle="Left hemisphere (blue) · Right hemisphere (red)"
        {...hemi}
        binEdges={binEdges} gapEnd={gapEnd} metadata={metaHemi}
      />
      <RegionChart
        title="ADR / TDR — Anterior"
        subtitle="ADR Left (blue) · ADR Right (red) · TDR bilateral (teal)"
        {...ant}
        binEdges={binEdges} gapEnd={gapEnd} metadata={metaAnt}
      />
      <RegionChart
        title="ADR / TDR — Posterior"
        subtitle="ADR Left (blue) · ADR Right (red) · TDR bilateral (teal)"
        {...post}
        binEdges={binEdges} gapEnd={gapEnd} metadata={metaPost}
      />
    </>
  );
}
