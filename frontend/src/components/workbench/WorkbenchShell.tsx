/**
 * WorkbenchShell — v2 layout.
 *
 * 3-column: [52px icon rail] | [main content] | [300px inspector]
 *
 * Dashboard view: adds RecordingHeader → KpiStrip → PanelSwitcher → TimeAxis
 * above the existing PatientDashboard (which still owns data fetching + panel render).
 * The Inspector sidebar replaces the old sidebar's pipeline-settings section.
 */

import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ImportView } from "@/components/import/ImportView";
import { PatientList } from "@/components/batch/PatientList";
import { ComparisonView } from "@/components/batch/ComparisonView";
import { ExportView } from "@/components/export/ExportView";
import { PatientDashboard } from "@/components/dashboard/PatientDashboard";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useAppStore } from "@/stores/appStore";

import { IconRail } from "./IconRail";
import { RecordingHeader } from "./RecordingHeader";
import { KpiStrip } from "./KpiStrip";
import { PanelSwitcher } from "./PanelSwitcher";
import { TimeAxis } from "./TimeAxis";
import { Inspector } from "./Inspector";

function DashboardView() {
  const patientId = useAppStore((s) => s.patientId);

  if (!patientId) {
    return (
      <div className="flex items-center justify-center h-full p-20 text-muted-foreground text-sm">
        Select a patient from the Patient List to view the dashboard.
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
      <RecordingHeader />
      <KpiStrip />
      <PanelSwitcher />
      <div className="flex-1 overflow-y-auto min-h-0">
        <TimeAxis />
        <ErrorBoundary>
          <PatientDashboard />
        </ErrorBoundary>
      </div>
    </div>
  );
}

export function WorkbenchShell({ healthBanner }: { healthBanner?: React.ReactNode }) {
  const view = useAppStore((s) => s.view);
  const patientId = useAppStore((s) => s.patientId);
  const isDashboard = view === "dashboard";

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      <IconRail />

      <main className="flex-1 flex flex-col min-h-0 min-w-0">
        {healthBanner}

        {isDashboard ? (
          <DashboardView />
        ) : (
          <ScrollArea className="flex-1 h-0">
            <ErrorBoundary>
              {view === "import"   && <ImportView />}
              {view === "patients" && <PatientList />}
              {view === "compare"  && <ComparisonView />}
              {view === "export"   && <ExportView />}
            </ErrorBoundary>
          </ScrollArea>
        )}
      </main>

      {isDashboard && patientId && <Inspector />}
    </div>
  );
}
