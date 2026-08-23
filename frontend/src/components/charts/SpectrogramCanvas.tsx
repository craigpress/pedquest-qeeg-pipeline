import { useRef, useEffect, useMemo, useState } from "react";
import { getColorScale, buildColorLUT } from "@/lib/colorScales";
import type { SpectrogramData } from "@/types/api";

interface SpectrogramCanvasProps {
  data: SpectrogramData;
  width?: number;
  height?: number;
  sharedMin?: number;
  sharedMax?: number;
  colorScale?: string;
}

function niceTimeStep(hoursRange: number, maxTicks: number): number {
  if (!Number.isFinite(hoursRange) || hoursRange <= 0) return 1;
  const target = hoursRange / Math.max(1, maxTicks);
  const magnitude = 10 ** Math.floor(Math.log10(target));
  for (const mult of [1, 2, 5, 10]) {
    const step = mult * magnitude;
    if (step >= target) return step;
  }
  return 10 * magnitude;
}

export function SpectrogramCanvas({ data, width, height = 180, sharedMin, sharedMax, colorScale }: SpectrogramCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(width ?? 600);

  const effectiveScale = colorScale ?? data.colorscale;
  const lut = useMemo(() => {
    const scaleFn = getColorScale(effectiveScale);
    return buildColorLUT(scaleFn);
  }, [effectiveScale]);

  // Compute value range for normalization
  const { vMin, vMax } = useMemo(() => {
    // Use shared bounds if provided
    if (sharedMin !== undefined && sharedMax !== undefined) {
      return { vMin: sharedMin, vMax: sharedMax };
    }

    let min = Infinity;
    let max = -Infinity;
    for (const row of data.matrix) {
      for (const v of row) {
        // Finiteness, not just non-null: an AR-rejected value can arrive as
        // NaN, which passes `!= null` and would silently widen nothing here
        // but floor the pixel below.
        if (v != null && Number.isFinite(v)) {
          if (v < min) min = v;
          if (v > max) max = v;
        }
      }
    }
    if (!isFinite(min)) return { vMin: 0, vMax: 1 };
    // For diverging (RdBu), center at 0
    if (data.colorscale === "RdBu") {
      const absMax = Math.max(Math.abs(min), Math.abs(max));
      return { vMin: -absMax, vMax: absMax };
    }
    return { vMin: min, vMax: max };
  }, [data.matrix, data.colorscale, sharedMin, sharedMax]);

  // Measure container width dynamically
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Initial measurement
    setContainerWidth(container.clientWidth);

    // Setup ResizeObserver to track width changes
    const resizeObserver = new ResizeObserver(() => {
      setContainerWidth(container.clientWidth);
    });
    resizeObserver.observe(container);

    return () => resizeObserver.disconnect();
  }, []);

  useEffect(() => {
    let raf: number;
    raf = requestAnimationFrame(() => {
      const canvas = canvasRef.current;
      const container = containerRef.current;
      if (!canvas || !container) return;

      const actualPlotWidth = containerWidth - MARGIN_LEFT - MARGIN_RIGHT;
      const actualPlotHeight = height - MARGIN_TOP - MARGIN_BOTTOM;
      canvas.width = actualPlotWidth;
      canvas.height = actualPlotHeight;

      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const nFreqs = data.frequencies.length;
      const nTimes = data.hours.length;
      if (nFreqs === 0 || nTimes === 0) return;

      const imgData = ctx.createImageData(nTimes, nFreqs);
      const range = vMax - vMin || 1;

      for (let fi = 0; fi < nFreqs; fi++) {
        // Flip Y so low frequencies are at bottom
        const row = nFreqs - 1 - fi;
        const matRow = data.matrix[fi];
        if (!matRow) continue;
        for (let ti = 0; ti < nTimes; ti++) {
          const v = matRow[ti];
          const idx = (row * nTimes + ti) * 4;
          // Missing OR non-finite. An artifact-rejected epoch must read as a
          // gap; painting it at the bottom of the colour scale would show a
          // suppressed value as a real measurement.
          if (v == null || !Number.isFinite(v)) {
            imgData.data[idx + 0] = 30;
            imgData.data[idx + 1] = 30;
            imgData.data[idx + 2] = 30;
            imgData.data[idx + 3] = 255;
          } else {
            const t = Math.max(0, Math.min(255, Math.round(((v - vMin) / range) * 255)));
            imgData.data[idx + 0] = lut[t * 4 + 0];
            imgData.data[idx + 1] = lut[t * 4 + 1];
            imgData.data[idx + 2] = lut[t * 4 + 2];
            imgData.data[idx + 3] = 255;
          }
        }
      }

      // Draw to offscreen canvas at native resolution, then scale
      const offscreen = new OffscreenCanvas(nTimes, nFreqs);
      const offCtx = offscreen.getContext("2d")!;
      offCtx.putImageData(imgData, 0, 0);

      // Align spectrogram image to the time axis (which starts at 0h).
      // When data starts after hour 0 (e.g. EEG starts 1h after ROSC),
      // offset the image so it aligns with the correct time position.
      const dataHoursMin = data.hours[0];
      const dataHoursMax = data.hours[data.hours.length - 1];
      const axisHoursMax = dataHoursMax; // axis ends at last data point
      const axisRange = axisHoursMax || 1; // axis starts at 0

      const dataStartPx = (dataHoursMin / axisRange) * actualPlotWidth;
      const dataEndPx = (dataHoursMax / axisRange) * actualPlotWidth;
      const dataWidthPx = dataEndPx - dataStartPx;

      ctx.imageSmoothingEnabled = false;
      ctx.clearRect(0, 0, actualPlotWidth, actualPlotHeight);
      ctx.drawImage(offscreen, dataStartPx, 0, dataWidthPx, actualPlotHeight);
    });
    return () => cancelAnimationFrame(raf);
  }, [data, lut, vMin, vMax, width, height, containerWidth]);

  // Axis layout constants — match Recharts chart alignment:
  // margin.left (5px) + YAxis width (56px) = 61px; margin.right (5px)
  const MARGIN_LEFT = 61;
  const MARGIN_BOTTOM = 32;
  const MARGIN_RIGHT = 5;
  const MARGIN_TOP = 8;
  const plotWidth = containerWidth - MARGIN_LEFT - MARGIN_RIGHT;
  const plotHeight = height - MARGIN_TOP - MARGIN_BOTTOM;

  // Generate time and frequency tick labels
  const hoursMin = 0;
  const hoursMax = data.hours[data.hours.length - 1];
  const hoursRange = hoursMax - hoursMin || 1;
  const maxTimeTicks = Math.max(2, Math.floor(plotWidth / 90));
  const timeStep = niceTimeStep(hoursRange, maxTimeTicks);
  const timeTicks = [];
  for (let h = Math.ceil(hoursMin / timeStep) * timeStep; h <= hoursMax; h += timeStep) {
    timeTicks.push(h);
  }
  if (timeTicks[0] !== 0) timeTicks.unshift(0);
  const lastTick = timeTicks[timeTicks.length - 1];
  if (hoursMax - lastTick > timeStep * 0.4) timeTicks.push(hoursMax);

  const maxFreq = data.frequencies[data.frequencies.length - 1] || 20;
  const freqTicks = [0, Math.round(maxFreq / 4), Math.round(maxFreq / 2), Math.round((3 * maxFreq) / 4), maxFreq];

  return (
    <div ref={containerRef} className="w-full" style={{ position: "relative", display: "block" }}>
      {/* SVG axes overlay — responsive width, absolute positioning */}
      <svg
        width={containerWidth}
        height={height}
        style={{ position: "absolute", top: 0, left: 0, pointerEvents: "none", overflow: "visible" }}
      >
        {/* Y-axis (frequency) */}
        <line x1={MARGIN_LEFT} y1={MARGIN_TOP} x2={MARGIN_LEFT} y2={height - MARGIN_BOTTOM} stroke="var(--border)" strokeWidth="1" />

        {/* X-axis (time) — extends to right edge minus margin */}
        <line x1={MARGIN_LEFT} y1={height - MARGIN_BOTTOM} x2={containerWidth - MARGIN_RIGHT} y2={height - MARGIN_BOTTOM} stroke="var(--border)" strokeWidth="1" />

        {/* Y-axis ticks and labels (frequency) */}
        {freqTicks.map((f) => {
          const y = height - MARGIN_BOTTOM - (f / maxFreq) * plotHeight;
          return (
            <g key={`freq-${f}`}>
              <line x1={MARGIN_LEFT - 5} y1={y} x2={MARGIN_LEFT} y2={y} stroke="var(--muted-foreground)" strokeWidth="1" />
              <text
                x={MARGIN_LEFT - 10}
                y={y}
                textAnchor="end"
                dominantBaseline="middle"
                fontSize="11"
                fill="var(--muted-foreground)"
              >
                {f}
              </text>
            </g>
          );
        })}

        {/* X-axis ticks and labels (time) */}
        {timeTicks.map((h) => {
          const x = MARGIN_LEFT + ((h - hoursMin) / hoursRange) * plotWidth;
          return (
            <g key={`time-${h}`}>
              <line x1={x} y1={height - MARGIN_BOTTOM} x2={x} y2={height - MARGIN_BOTTOM + 5} stroke="var(--muted-foreground)" strokeWidth="1" />
              <text
                x={x}
                y={height - MARGIN_BOTTOM + 12}
                textAnchor="middle"
                fontSize="10"
                fill="var(--muted-foreground)"
              >
                {`${Math.round(h)}h`}
              </text>
            </g>
          );
        })}

        {/* Y-axis label */}
        <text
          x={15}
          y={height / 2}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="11"
          fill="var(--muted-foreground)"
          transform={`rotate(-90 15 ${height / 2})`}
        >
          Frequency (Hz)
        </text>

        {/* X-axis label */}
        <text
          x={MARGIN_LEFT + plotWidth / 2}
          y={height - 2}
          textAnchor="middle"
          fontSize="11"
          fill="var(--muted-foreground)"
        >
          Time (hours)
        </text>
      </svg>

      {/* Canvas container with padding to match SVG axes */}
      <div style={{ paddingLeft: MARGIN_LEFT, paddingTop: MARGIN_TOP, paddingRight: MARGIN_RIGHT, paddingBottom: MARGIN_BOTTOM }}>
        <canvas
          ref={canvasRef}
          className="w-full rounded"
          style={{
            height: plotHeight,
            imageRendering: "pixelated",
            display: "block"
          }}
        />
      </div>
    </div>
  );
}
