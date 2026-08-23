import { useCallback } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import { useAppStore } from "@/stores/appStore";

/**
 * Returns a DOM `onMouseMove` handler for the panel's chart stack. Moving the
 * mouse anywhere over the charts maps the pointer's x position to the shared
 * `cursorPct`, so the cursor line and the Inspector sidebar follow the mouse.
 *
 * Recharts 3.x does not reliably invoke the chart-level `onMouseMove` prop, so
 * we attach a plain DOM listener on the container (events bubble up from each
 * chart) and derive the fraction from the hovered chart's cartesian-grid rect —
 * which spans exactly the plot area and excludes the Y axis, so it stays aligned
 * with the CursorLine and TimeAxis regardless of Y-axis width. `setCursorPct`
 * clamps to 0..1, so positions over the gutters are handled safely.
 */
export function useCursorTracking() {
  const setCursorPct = useAppStore((s) => s.setCursorPct);

  return useCallback(
    (e: ReactMouseEvent<HTMLElement>) => {
      const wrapper = (e.target as Element)?.closest?.(".recharts-wrapper");
      if (!wrapper) return;
      const plot = wrapper.querySelector(".recharts-cartesian-grid") ?? wrapper;
      const rect = plot.getBoundingClientRect();
      if (rect.width <= 0) return;
      setCursorPct((e.clientX - rect.left) / rect.width);
    },
    [setCursorPct],
  );
}
