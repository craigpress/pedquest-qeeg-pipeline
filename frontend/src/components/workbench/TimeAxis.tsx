import { useEffect, useRef, useState } from "react";
import { useAppStore } from "@/stores/appStore";

function fmtTime(pct: number, totalHours: number): string {
  const totalSec = Math.round(pct * totalHours * 3600);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function TimeAxis() {
  const summary = useAppStore((s) => s.patientSummary);
  const cursorPct = useAppStore((s) => s.cursorPct);
  const setCursorPct = useAppStore((s) => s.setCursorPct);
  const trackRef = useRef<HTMLDivElement>(null);
  const [trackWidth, setTrackWidth] = useState(0);

  // When EEG starts after ROSC, the timeline runs from 0 (ROSC) to
  // hours_rosc_to_eeg + recording_duration so the cursor maps to the same
  // ROSC-relative x-axis used by all charts.
  const roscOffset = Math.max(0, summary?.time_axis?.hours_rosc_to_eeg ?? 0);
  const totalHours = roscOffset + (summary?.qc.recording_duration_hours ?? 12);
  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    setTrackWidth(track.clientWidth);
    const observer = new ResizeObserver(() => setTrackWidth(track.clientWidth));
    observer.observe(track);
    return () => observer.disconnect();
  }, []);

  // Produce evenly-spaced ticks from 0 to totalHours without crowding labels.
  // Each tick is positioned at exactly (t/totalHours)*100% so the last tick
  // always sits at the right edge of the track and its label matches totalHours.
  const maxTickCount = Math.max(2, Math.floor((trackWidth || 600) / 92));
  const tickCount = Math.min(maxTickCount, Math.max(1, Math.floor(totalHours)));
  const ticks = Array.from({ length: tickCount + 1 }, (_, i) => (i / tickCount) * totalHours);

  const onMouseDown = (e: React.MouseEvent) => {
    const track = trackRef.current;
    if (!track) return;

    const update = (clientX: number) => {
      const rect = track.getBoundingClientRect();
      setCursorPct((clientX - rect.left) / rect.width);
    };

    update(e.clientX);

    const onMove = (ev: MouseEvent) => update(ev.clientX);
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  return (
    <div className="sticky top-0 z-10 flex items-stretch px-4 py-2 border-b border-border bg-card">
      {/* Left gutter: matches CardContent px-2 (8px) + Recharts margin.left (5px) + YAxis width (56px) = 69px */}
      <div className="shrink-0 w-[69px] flex items-center">
        <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">Time</span>
      </div>

      {/* Track */}
      <div
        ref={trackRef}
        onMouseDown={onMouseDown}
        data-testid="time-axis-track"
        className="relative flex-1 h-9 border border-border rounded cursor-crosshair select-none overflow-hidden bg-muted/30"
      >
        {/* Proportional gridlines — interior ticks only, same positions as labels */}
        {ticks.slice(1, -1).map((t) => (
          <div
            key={t}
            className="absolute top-0 bottom-0 w-px bg-border pointer-events-none"
            style={{ left: `${(t / totalHours) * 100}%` }}
          />
        ))}

        {/* Hour labels — absolutely positioned so last label aligns to right edge */}
        {ticks.map((t, i) => {
          const pct = (t / totalHours) * 100;
          const isFirst = i === 0;
          const isLast = i === ticks.length - 1;
          return (
            <span
              key={i}
              className="absolute top-0.5 font-mono text-[10px] text-muted-foreground pointer-events-none pl-0.5"
              style={{
                left: `${pct}%`,
                transform: isFirst ? "none" : isLast ? "translateX(-100%)" : "translateX(-50%)",
              }}
            >
              {Math.round(t)}h
            </span>
          );
        })}

        {/* Cursor line */}
        <div
          className="absolute top-0 bottom-0 w-px bg-foreground pointer-events-none z-10"
          style={{ left: `${cursorPct * 100}%` }}
        >
          <div
            className="absolute top-0.5 bg-foreground text-background font-mono text-[10px] px-1 rounded whitespace-nowrap"
            style={{
              left: cursorPct > 0.85 ? "auto" : "6px",
              right: cursorPct > 0.85 ? "6px" : "auto",
            }}
          >
            {fmtTime(cursorPct, totalHours)}
          </div>
        </div>
      </div>

      {/* Right gutter: matches Recharts margin.right (5px) + CardContent px-2 (8px) = 13px */}
      <div className="shrink-0 w-[13px]" aria-hidden />
    </div>
  );
}
