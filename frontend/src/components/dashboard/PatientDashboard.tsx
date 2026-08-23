import { useEffect } from "react";
import { useAppStore } from "@/stores/appStore";
import { getOverlayData } from "@/api/client";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { useChartMetadata } from "@/hooks/useChartMetadata";

import { BinStatistics } from "@/components/charts/BinStatistics";
import { PersystPanel } from "@/components/panels/PersystPanel";

const SUMMARY_STATS_VALUE = "__summary_stats__";

export function PatientDashboard() {
  const patientId = useAppStore((s) => s.patientId);
  const setOverlayData = useAppStore((s) => s.setOverlayData);
  const activePanel = useAppStore((s) => s.activePanel);
  const reprocessTrigger = useAppStore((s) => s.reprocessTrigger);
  const summary = useAppStore((s) => s.patientSummary);

  // Fetch chart metadata once per patient (cached in store); still used for legacy info panels.
  useChartMetadata();

  // Overlay data (artifact regions, bin boundaries, gaps) — load once per patient/reprocess.
  // Spectrogram loading is now owned by `PersystPanel` + `useSpectrogramBundle`, so this
  // effect only covers the overlay fetch.
  useEffect(() => {
    setOverlayData(null);
    if (!patientId) return;

    const ctrl = new AbortController();
    const { signal } = ctrl;
    getOverlayData(patientId, signal)
      .then((d) => {
        if (!signal.aborted) setOverlayData(d);
      })
      .catch(() => {});
    return () => ctrl.abort();
  }, [patientId, reprocessTrigger, setOverlayData]);

  return (
    <div className="p-4 space-y-4">
      {/* Clinical timing info bar */}
      {summary?.time_axis && (
        <div className="flex items-center gap-4 flex-wrap text-xs">
          <div className="flex items-center gap-1">
            <span className="text-[13px] text-muted-foreground">Time Zero:</span>
            <span className="text-[13px] font-medium">
              {summary.time_axis.reference === "rosc" ? "ROSC" : "Recording Start"}
            </span>
          </div>

          <div className="flex items-center gap-1">
            {summary.time_axis.age_at_arrest_days != null ? (
              <>
                <span className="text-[13px] text-muted-foreground">Age at ROSC:</span>
                <span className="text-[13px] font-mono font-medium">
                  {summary.time_axis.age_at_arrest_days} days
                  {summary.time_axis.rosc_time ? `, ${summary.time_axis.rosc_time}` : ""}
                </span>
              </>
            ) : !summary.time_axis.date_shifted && summary.time_axis.rosc_date ? (
              <>
                <span className="text-[13px] text-muted-foreground">ROSC:</span>
                <span className="text-[13px] font-mono font-medium">
                  {summary.time_axis.rosc_date}
                  {summary.time_axis.rosc_time ? ` ${summary.time_axis.rosc_time}` : ""}
                </span>
              </>
            ) : summary.time_axis.rosc_time ? (
              <>
                <span className="text-[13px] text-muted-foreground">ROSC Time:</span>
                <span className="text-[13px] font-mono font-medium">{summary.time_axis.rosc_time}</span>
              </>
            ) : (
              <>
                <span className="text-[13px] text-muted-foreground">ROSC:</span>
                <span className="text-[13px] font-mono text-muted-foreground">Not available</span>
              </>
            )}
          </div>

          <div className="flex items-center gap-1">
            {summary.time_axis.age_at_eeg_start_days != null ? (
              <>
                <span className="text-[13px] text-muted-foreground">Age at EEG Start:</span>
                <span className="text-[13px] font-mono font-medium">
                  {summary.time_axis.age_at_eeg_start_days} days
                  {summary.time_axis.eeg_start_time ? `, ${summary.time_axis.eeg_start_time}` : ""}
                </span>
              </>
            ) : !summary.time_axis.date_shifted && summary.time_axis.eeg_start_date ? (
              <>
                <span className="text-[13px] text-muted-foreground">EEG Start:</span>
                <span className="text-[13px] font-mono font-medium">
                  {summary.time_axis.eeg_start_date}
                  {summary.time_axis.eeg_start_time ? ` ${summary.time_axis.eeg_start_time}` : ""}
                </span>
              </>
            ) : summary.time_axis.eeg_start_time ? (
              <>
                <span className="text-[13px] text-muted-foreground">EEG Start:</span>
                <span className="text-[13px] font-mono font-medium">{summary.time_axis.eeg_start_time}</span>
              </>
            ) : (
              <>
                <span className="text-[13px] text-muted-foreground">EEG Start:</span>
                <span className="text-[13px] font-mono text-muted-foreground">Not available</span>
              </>
            )}
          </div>

          {summary.time_axis.hours_rosc_to_eeg != null && (
            <span className="text-[13px] font-mono font-medium bg-muted px-1.5 py-0.5 rounded">
              ROSC→EEG: {summary.time_axis.hours_rosc_to_eeg}h
            </span>
          )}

          {summary.time_axis.date_shifted && (
            <span className="text-[13px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
              Date-shifted
            </span>
          )}
        </div>
      )}


      {activePanel === SUMMARY_STATS_VALUE ? (
        <ErrorBoundary panel>
          <BinStatistics />
        </ErrorBoundary>
      ) : (
        <ErrorBoundary panel>
          <PersystPanel panelId={activePanel} />
        </ErrorBoundary>
      )}
    </div>
  );
}
