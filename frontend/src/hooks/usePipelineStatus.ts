/** Hook for subscribing to pipeline SSE progress. */
import { useEffect, useRef } from "react";
import { subscribePipelineStatus } from "@/api/client";
import { useAppStore } from "@/stores/appStore";
import { clearPatientDataCache } from "@/hooks/usePatientData";
import type { PipelineProgress } from "@/types/api";

export function usePipelineStatus(jobId: string | null): void {
  const setPipelineStatus = useAppStore((s) => s.setPipelineStatus);
  const unsubRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (!jobId) return;

    setPipelineStatus("running", 0, "Starting...");

    unsubRef.current = subscribePipelineStatus(
      jobId,
      (p: PipelineProgress) => {
        setPipelineStatus("running", p.progress, p.message);
      },
      (p: PipelineProgress) => {
        if (p.patient_id) {
          clearPatientDataCache(p.patient_id);
        }
        setPipelineStatus("complete", 1, "Pipeline complete");
      },
      (err: string) => {
        setPipelineStatus("error", 0, err);
      },
    );

    return () => {
      unsubRef.current?.();
    };
  }, [jobId, setPipelineStatus]);
}
