import { describe, it, expect } from "vitest";

import { PANELS, findPanel } from "../manifest";
import { validateManifest } from "../manifest.validate";

describe("panel manifest integrity", () => {
  it("is non-empty", () => {
    expect(PANELS.length).toBeGreaterThan(0);
  });

  it("has unique panel IDs", () => {
    const ids = PANELS.map((p) => p.panelId);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("passes validateManifest (no missing/colliding spectrogram freq ranges)", () => {
    // This is the load-time invariant the app throws on; assert it as a test so
    // a manifest edit that breaks it fails CI instead of only failing at runtime.
    expect(() => validateManifest(PANELS)).not.toThrow();
  });

  it("findPanel resolves every declared panel and rejects unknown ids", () => {
    for (const p of PANELS) {
      expect(findPanel(p.panelId)?.panelId).toBe(p.panelId);
    }
    expect(findPanel("__does_not_exist__")).toBeNull();
  });

  it("every group has at least one row", () => {
    for (const p of PANELS) {
      for (const g of p.groups) {
        expect(g.rows.length).toBeGreaterThan(0);
      }
    }
  });
});
