import { Activity, Download, FileText, Moon, Sun, Users } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import type { ViewMode } from "@/stores/appStore";

interface NavItem {
  view: ViewMode;
  icon: React.ReactNode;
  label: string;
  requiresPatient?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { view: "import",    icon: <FileText className="h-4 w-4" />,  label: "Import" },
  { view: "patients",  icon: <Users className="h-4 w-4" />,     label: "Patients" },
  { view: "dashboard", icon: <Activity className="h-4 w-4" />,  label: "Dashboard", requiresPatient: true },
  { view: "export",    icon: <Download className="h-4 w-4" />,  label: "Export" },
];

export function IconRail() {
  const view = useAppStore((s) => s.view);
  const setView = useAppStore((s) => s.setView);
  const patientId = useAppStore((s) => s.patientId);
  const theme = useAppStore((s) => s.theme);
  const toggleTheme = useAppStore((s) => s.toggleTheme);

  return (
    <nav
      className="flex flex-col items-center gap-1 py-2 border-r border-border bg-muted/40"
      style={{ width: 52, flexShrink: 0 }}
    >
      {/* Logo mark */}
      <div className="mb-2 w-8 h-8 rounded-md bg-foreground text-background flex items-center justify-center font-mono text-[10px] font-semibold select-none">
        qE
      </div>

      {NAV_ITEMS.map((item) => {
        const disabled = item.requiresPatient && !patientId;
        const active = view === item.view;
        return (
          <button
            key={item.view}
            onClick={() => !disabled && setView(item.view)}
            disabled={disabled}
            title={item.label}
            className={[
              "relative w-9 h-9 flex items-center justify-center rounded-md transition-colors",
              active
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
              disabled ? "opacity-30 cursor-not-allowed" : "cursor-pointer",
            ].join(" ")}
          >
            {active && (
              <span className="absolute left-[-10px] top-2 bottom-2 w-0.5 rounded-r bg-foreground" />
            )}
            {item.icon}
          </button>
        );
      })}

      <div className="flex-1" />

      <button
        onClick={toggleTheme}
        title="Toggle theme"
        className="w-9 h-9 flex items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
      >
        {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </button>
    </nav>
  );
}
