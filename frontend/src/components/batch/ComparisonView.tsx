import { useState, useEffect } from "react";
import { Database } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { listPatients, comparePatients } from "@/api/client";
import type { PatientSummary, ComparisonData } from "@/types/api";

export function ComparisonView() {
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [comparison, setComparison] = useState<ComparisonData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listPatients().then(setPatients).catch(console.error);
  }, []);

  function toggleSelect(pid: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(pid)) next.delete(pid);
      else if (next.size < 4) next.add(pid);
      return next;
    });
  }

  async function runComparison() {
    if (selected.size < 2) return;
    setLoading(true);
    try {
      const data = await comparePatients(Array.from(selected));
      setComparison(data);
    } catch (err) {
      console.error("Comparison failed:", err);
    } finally {
      setLoading(false);
    }
  }

  if (patients.length < 2) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-20 gap-4">
        <Database className="h-12 w-12 text-muted-foreground/50" />
        <p className="text-muted-foreground text-sm">
          Process at least 2 patients to use comparison view.
        </p>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Compare Patients</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Select 2-4 patients to compare metrics
        </p>
      </div>

      {/* Patient selector */}
      <div className="flex flex-wrap gap-2">
        {patients.map((p) => (
          <Badge
            key={p.patient_id}
            variant={selected.has(p.patient_id) ? "default" : "outline"}
            className="cursor-pointer text-xs py-1 px-3"
            onClick={() => toggleSelect(p.patient_id)}
          >
            {p.patient_id}
          </Badge>
        ))}
      </div>

      <Button
        onClick={runComparison}
        disabled={selected.size < 2 || loading}
      >
        {loading ? "Comparing..." : `Compare ${selected.size} Patients`}
      </Button>

      {/* Results */}
      {comparison && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Patient-level metrics */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Patient-Level Metrics</CardTitle>
            </CardHeader>
            <CardContent>
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="text-muted-foreground text-[10px]">
                    <th className="text-left py-1">Metric</th>
                    {comparison.patient_ids.map((pid) => (
                      <th key={pid} className="text-right py-1">{pid}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {["artifact_pct", "usable_hours", "recording_hours", "seizure_burden_pct", "seizure_events"].map(
                    (metric) => (
                      <tr key={metric} className="border-t border-border/50">
                        <td className="py-1 text-muted-foreground">{metric}</td>
                        {comparison.patient_ids.map((pid) => {
                          const m = comparison.metrics.find(
                            (x) => x.patient_id === pid && x.metric_name === metric && !x.bin_label,
                          );
                          return (
                            <td key={pid} className="text-right py-1">
                              {m?.value != null ? m.value.toFixed(2) : "-"}
                            </td>
                          );
                        })}
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </CardContent>
          </Card>

          {/* Bin-level summary */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Bin Coverage</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xs text-muted-foreground">
                Bin-level metric comparison available after selecting specific features.
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
