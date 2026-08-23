import { useEffect } from "react";
import { useAppStore } from "@/stores/appStore";
import { getPatient } from "@/api/client";

/**
 * On a hard reload the persisted `patientId` is restored from localStorage, but
 * `patientSummary` is not (it is not persisted). Without this, the dashboard
 * loads in a half-populated state — charts render but the Inspector, header
 * stats, TimeAxis, and cursor read "no patient" because the summary is null.
 *
 * This refetches the summary once on mount. The post-fetch patientId guard
 * avoids clobbering a newer selection if the user navigates while the request
 * is in flight; a failure (e.g. the saved patient was deleted) clears the stale
 * selection so the app falls back to the import view instead of staying broken.
 */
export function useRestorePatientSummary() {
  useEffect(() => {
    const { patientId, patientSummary, setPatient } = useAppStore.getState();
    if (!patientId || patientSummary) return;

    let cancelled = false;
    getPatient(patientId)
      .then((summary) => {
        if (cancelled || useAppStore.getState().patientId !== patientId) return;
        useAppStore.setState({ patientSummary: summary });
      })
      .catch(() => {
        if (cancelled || useAppStore.getState().patientId !== patientId) return;
        setPatient(null);
      });

    return () => {
      cancelled = true;
    };
  }, []);
}
