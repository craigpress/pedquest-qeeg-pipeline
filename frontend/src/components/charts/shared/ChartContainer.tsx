import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Info, ChevronDown } from "lucide-react";
import type { ChartPanelMetadata } from "@/types/api";

interface ChartContainerProps {
  title: string;
  subtitle?: string;
  height?: number | "auto";
  metadata?: ChartPanelMetadata | null;
  headerExtra?: React.ReactNode;
  children: React.ReactNode;
}

export function ChartContainer({ title, subtitle, height = 200, metadata, headerExtra, children }: ChartContainerProps) {
  const [infoOpen, setInfoOpen] = useState(false);

  return (
    <Card className="py-0">
      <CardHeader className="pb-0.5 pt-1 px-3">
        <div className="flex items-center gap-1.5">
          <CardTitle className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
            {title}
          </CardTitle>
          {metadata && (
            <button
              type="button"
              onClick={() => setInfoOpen((v) => !v)}
              className="inline-flex items-center justify-center rounded p-0.5 text-muted-foreground/50 hover:text-muted-foreground hover:bg-muted/50 transition-colors"
              aria-label={infoOpen ? "Hide chart info" : "Show chart info"}
              aria-expanded={infoOpen}
            >
              <Info className="h-3 w-3" />
              <ChevronDown
                className={`h-2.5 w-2.5 ml-0.5 transition-transform duration-150 ${infoOpen ? "rotate-180" : ""}`}
              />
            </button>
          )}
          {headerExtra && <div className="ml-auto">{headerExtra}</div>}
        </div>
        {subtitle && (
          <p className="text-xs text-muted-foreground/70">{subtitle}</p>
        )}

        {/* Expandable info panel */}
        {metadata && infoOpen && (
          <div className="mt-1.5 rounded border border-border/50 bg-muted/30 px-3 py-2 text-xs leading-relaxed text-muted-foreground space-y-1.5">
            {metadata.description && (
              <p className="font-medium text-foreground/80">{metadata.description}</p>
            )}
            {metadata.variables.length > 0 && (
              <div className="flex gap-1 flex-wrap items-start">
                <span className="font-medium text-muted-foreground/80 shrink-0 mt-0.5">Variables:</span>
                {metadata.variables.map((v) => (
                  <span key={v} className="inline-block bg-muted border border-border/40 rounded px-1.5 py-0.5 text-[11px] font-mono text-foreground/70 leading-tight">
                    {v}
                  </span>
                ))}
              </div>
            )}
            <InfoRow label="Source families" value={metadata.source_families.join(", ")} />
            {metadata.derivation && <InfoRow label="Derivation" value={metadata.derivation} />}
            <InfoRow label="Units" value={metadata.units} />
            <InfoRow
              label="Cadence / Window"
              value={`${metadata.cadence_seconds}s epoch / ${metadata.window_seconds}s window`}
            />
            {metadata.filtering && <InfoRow label="Filtering" value={metadata.filtering} />}
          </div>
        )}
      </CardHeader>
      <CardContent className="px-2 pb-1 pt-0" style={height === "auto" ? { minWidth: 1 } : { height, minHeight: 1, minWidth: 1 }}>
        <ErrorBoundary panel>
          {children}
        </ErrorBoundary>
      </CardContent>
    </Card>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <div className="flex gap-2">
      <span className="font-medium text-muted-foreground/80 shrink-0">{label}:</span>
      <span className="text-foreground/70">{value}</span>
    </div>
  );
}
