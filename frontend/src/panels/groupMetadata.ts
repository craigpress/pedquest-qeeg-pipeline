/**
 * Synthesise a `ChartPanelMetadata` shape from a SubChartGroup so that the
 * shared `ChartContainer` info-panel chevron stays populated in the rebuild.
 *
 * The backend `/chart-metadata` endpoint emits panel-keyed metadata that
 * predates the 8-panel rebuild; its panel_ids don't align with the new
 * instrument-row ids. Rather than extending the backend API in this pass,
 * we hand-author metadata directly from each group's rows.
 */

import type { SubChartGroup } from "./types";
import type { ChartPanelMetadata } from "@/types/api";
import { familiesForColumn } from "./columnResolver";

export function groupToMetadata(group: SubChartGroup): ChartPanelMetadata {
  const variables: string[] = [];
  const families = new Set<string>();
  const units = new Set<string>();

  for (const row of group.rows) {
    units.add(row.unit);
    for (const trace of row.traces) {
      if (trace.source.kind === "column") {
        variables.push(trace.source.key);
        for (const fam of familiesForColumn(trace.source.key)) families.add(fam);
      } else if (trace.source.kind === "spectrogram") {
        variables.push(`spectrogram:${trace.source.specType}`);
      } else if (trace.source.kind === "derived") {
        variables.push(`derived:${trace.source.fn}`);
      }
    }
  }

  return {
    panel_id: group.groupId,
    display_name: group.label,
    description: group.description,
    source_families: Array.from(families).sort(),
    variables,
    units: Array.from(units).filter(Boolean).join(" / "),
    derivation: group.rows.map((r) => r.persystName).join(" + "),
    cadence_seconds: 0,
    window_seconds: 0,
    filtering: "",
  };
}
