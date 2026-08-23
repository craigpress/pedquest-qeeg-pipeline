/**
 * Run-at-import validator for the panel manifest.
 *
 * Enforces the user's guarantee: no sub-chart group may contain two
 * spectrograms that cover the same Hz range. Any violation throws a loud
 * `Error` at module load — in dev this surfaces immediately via HMR; in
 * production the bundle fails to initialise, which is the intended behaviour
 * (the rebuild's whole point was to eliminate this class of bug).
 */

import type { PanelManifest } from "./types";

export function validateManifest(panels: PanelManifest[]): void {
  for (const panel of panels) {
    for (const group of panel.groups) {
      const specs = group.rows.filter((r) => r.kind === "spectrogram");
      if (specs.length < 2) continue;

      const seen = new Set<string>();
      for (const row of specs) {
        if (!row.freqRange) {
          throw new Error(
            `Panel "${panel.panelId}" group "${group.groupId}" has spectrogram row "${row.instrumentId}" without a freqRange declared.`,
          );
        }
        const key = `${row.freqRange[0]}-${row.freqRange[1]}`;
        if (seen.has(key)) {
          throw new Error(
            `Panel "${panel.panelId}" group "${group.groupId}" co-locates two spectrograms with identical freq range ${key} Hz. Fix the manifest or the overlapPrevious flag.`,
          );
        }
        seen.add(key);
      }
    }
  }
}
