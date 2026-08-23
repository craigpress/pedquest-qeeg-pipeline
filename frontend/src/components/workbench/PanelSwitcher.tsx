import { PANELS } from "@/panels/manifest";
import { useAppStore } from "@/stores/appStore";

const SUMMARY_STATS_ID = "__summary_stats__";

export function PanelSwitcher() {
  const activePanel = useAppStore((s) => s.activePanel);
  const setActivePanel = useAppStore((s) => s.setActivePanel);

  const btnClass = (id: string) =>
    [
      "px-2.5 py-1 text-[11.5px] font-medium rounded whitespace-nowrap transition-colors",
      activePanel === id
        ? "bg-background text-foreground shadow-sm"
        : "text-muted-foreground hover:text-foreground",
    ].join(" ");

  return (
    <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-card overflow-x-auto">
      {/* Clinical panels */}
      <div
        className="flex items-center gap-0.5 p-0.5 rounded-md bg-muted border border-border"
        role="group"
        aria-label="Clinical panels"
      >
        {PANELS.map((panel) => (
          <button
            key={panel.panelId}
            onClick={() => setActivePanel(panel.panelId)}
            className={btnClass(panel.panelId)}
          >
            {panel.displayName}
          </button>
        ))}
      </div>

      {/* Divider */}
      <div className="w-px h-5 bg-border shrink-0" />

      {/* Summary Stats */}
      <div
        className="flex items-center p-0.5 rounded-md bg-muted border border-border"
        role="group"
        aria-label="Summary"
      >
        <button
          onClick={() => setActivePanel(SUMMARY_STATS_ID)}
          className={btnClass(SUMMARY_STATS_ID)}
        >
          Summary Stats
        </button>
      </div>
    </div>
  );
}
