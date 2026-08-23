import { useEffect, useState } from "react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { healthCheck } from "@/api/client";
import { WorkbenchShell } from "@/components/workbench/WorkbenchShell";
import { useRestorePatientSummary } from "@/hooks/useRestorePatientSummary";

function HealthBanner() {
  const [offline, setOffline] = useState(false);
  const [retryIn, setRetryIn] = useState(0);

  useEffect(() => {
    let attempt = 0;
    let timer: ReturnType<typeof setTimeout>;

    async function check() {
      try {
        await healthCheck();
        setOffline(false);
        attempt = 0;
        timer = setTimeout(check, 30000);
      } catch {
        attempt++;
        setOffline(true);
        const delay = Math.min(2 ** attempt * 1000, 30000);
        setRetryIn(Math.round(delay / 1000));
        timer = setTimeout(check, delay);
      }
    }

    check();
    return () => clearTimeout(timer);
  }, []);

  if (!offline) return null;

  return (
    <div className="flex items-center justify-center gap-2 px-4 py-1.5 bg-amber-500/15 border-b border-amber-500/30 text-amber-400 text-xs">
      <span className="inline-block w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
      Backend unavailable — retrying in {retryIn}s
    </div>
  );
}

export default function App() {
  useRestorePatientSummary();
  return (
    <ErrorBoundary>
      <WorkbenchShell healthBanner={<HealthBanner />} />
    </ErrorBoundary>
  );
}
