import { useState, useEffect, useMemo, useImperativeHandle, forwardRef } from "react";
import type { ChangeEvent } from "react";
import { Loader2, Settings2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { listMmxConfigs, uploadMmx, uploadMmxFile, listStudies, createStudy } from "@/api/client";
import type { MmxConfigSummary, StudyInfo } from "@/types/api";
import { formatStudyLabel } from "@/lib/studyLabel";

export interface StudySelectorHandle {
  /** Creates the study on the backend if "new study" is selected. Returns true on success. */
  ensureStudyCreated: () => Promise<boolean>;
}

interface StudySelectorProps {
  onStudyChange: (studyName: string, mmxStudy?: string) => void;
}

export const StudySelector = forwardRef<StudySelectorHandle, StudySelectorProps>(
  function StudySelector({ onStudyChange }, ref) {
    const [studies, setStudies] = useState<StudyInfo[]>([]);
    const [mmxConfigs, setMmxConfigs] = useState<MmxConfigSummary[]>([]);
    const [selectedStudy, setSelectedStudy] = useState<string>("");
    const [isNewStudy, setIsNewStudy] = useState(false);
    const [newStudyName, setNewStudyName] = useState("");
    const [newStudyMmx, setNewStudyMmx] = useState<string>("");
    const [mmxPath, setMmxPath] = useState("");
    const [mmxUploading, setMmxUploading] = useState(false);
    const [mmxError, setMmxError] = useState<string | null>(null);

    useEffect(() => {
      listStudies().then(setStudies).catch(() => {});
      listMmxConfigs().then(setMmxConfigs).catch(() => {});
    }, []);

    const effectiveMmxStudy = useMemo(() => {
      if (isNewStudy) return newStudyMmx || undefined;
      if (selectedStudy) {
        const study = studies.find((s) => s.name === selectedStudy);
        return study?.mmx_study || undefined;
      }
      return undefined;
    }, [isNewStudy, selectedStudy, studies, newStudyMmx]);

    const effectiveStudyName = isNewStudy ? newStudyName.trim() || undefined : selectedStudy || undefined;

    useEffect(() => {
      onStudyChange(effectiveStudyName ?? "", effectiveMmxStudy);
    }, [effectiveStudyName, effectiveMmxStudy]);

    useImperativeHandle(ref, () => ({
      async ensureStudyCreated() {
        if (isNewStudy && newStudyName.trim()) {
          try {
            await createStudy(newStudyName.trim(), newStudyMmx || undefined);
            const updated = await listStudies();
            setStudies(updated);
            return true;
          } catch (e) {
            setMmxError(e instanceof Error ? e.message : String(e));
            return false;
          }
        }
        return true;
      },
    }));

    function handleStudyChange(value: string) {
      if (value === "__new__") {
        setIsNewStudy(true);
        setSelectedStudy("");
      } else {
        setIsNewStudy(false);
        setSelectedStudy(value);
      }
    }

    // The MMX config is keyed by the study it belongs to, so an upload made
    // while an existing study is selected must attach to that study, not to
    // the "new study" name box.
    const mmxTargetLabel = effectiveStudyName || "uploaded";

    /** Persist `label` as the selected study's MMX config. */
    async function attachMmx(label: string | undefined) {
      if (isNewStudy || !selectedStudy) {
        setNewStudyMmx(label ?? "");
        return;
      }
      // create_study is an upsert and rewrites every field — pass the study's
      // current date_shifted back or attaching an MMX silently clears it.
      const existing = studies.find((s) => s.name === selectedStudy);
      await createStudy(selectedStudy, label || undefined, existing?.date_shifted ?? false);
      setStudies(await listStudies());
    }

    /** Shared upload wrapper. Returns true if the MMX was stored. */
    async function runMmxUpload(
      upload: (label: string) => Promise<unknown>,
    ): Promise<boolean> {
      setMmxUploading(true);
      setMmxError(null);
      try {
        await upload(mmxTargetLabel);
        setMmxConfigs(await listMmxConfigs());
        await attachMmx(mmxTargetLabel);
        return true;
      } catch (e) {
        setMmxError(e instanceof Error ? e.message : String(e));
        return false;
      } finally {
        setMmxUploading(false);
      }
    }

    async function handleMmxUpload() {
      if (!mmxPath.trim()) return;
      const cleanMmxPath = mmxPath.trim().replace(/^["']+|["']+$/g, "");
      const ok = await runMmxUpload((label) => uploadMmx(cleanMmxPath, label));
      if (ok) setMmxPath("");
    }

    async function handleMmxFile(e: ChangeEvent<HTMLInputElement>) {
      const file = e.target.files?.[0];
      e.target.value = ""; // allow re-picking the same file after an error
      if (!file) return;
      await runMmxUpload((label) => uploadMmxFile(file, label));
    }

    async function handleMmxConfigChange(value: string) {
      setMmxError(null);
      try {
        await attachMmx(value || undefined);
      } catch (e) {
        setMmxError(e instanceof Error ? e.message : String(e));
      }
    }

    return (
      <div className="border rounded-lg p-3 space-y-2 bg-muted/20">
        <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <Settings2 className="h-3.5 w-3.5" />
          Study
        </div>

        <div className="flex items-center gap-2 text-xs">
          <label className="text-muted-foreground whitespace-nowrap">
            Select study:
          </label>
          <select
            value={isNewStudy ? "__new__" : selectedStudy}
            onChange={(e) => handleStudyChange(e.target.value)}
            className="flex-1 bg-background border border-border rounded px-2 py-1 text-xs"
          >
            <option value="">No study (use defaults)</option>
            {studies.map((s) => (
              <option key={s.name} value={s.name}>
                {formatStudyLabel(s.name)}{s.mmx_study ? ` (MMX: ${s.mmx_study})` : ""} — {s.patient_count} patients
              </option>
            ))}
            <option value="__new__">+ New study...</option>
          </select>
        </div>

        {isNewStudy && (
          <div className="space-y-2 pl-2 border-l-2 border-primary/30">
            <div className="flex items-center gap-2 text-xs">
              <input
                type="text"
                placeholder="Study name (e.g. PedQuEST)"
                value={newStudyName}
                onChange={(e) => setNewStudyName(e.target.value)}
                className="flex-1 bg-background border border-border rounded px-2 py-1 text-xs"
              />
            </div>
          </div>
        )}

        <div className="space-y-2 pt-1 border-t border-border/50">
          {mmxConfigs.length > 0 && (
            <div className="flex items-center gap-2 text-xs">
              <label className="text-muted-foreground whitespace-nowrap">
                MMX config:
              </label>
              <select
                value={effectiveMmxStudy ?? ""}
                onChange={(e) => handleMmxConfigChange(e.target.value)}
                className="flex-1 bg-background border border-border rounded px-2 py-1 text-xs"
              >
                <option value="">No MMX (use defaults)</option>
                {mmxConfigs.map((cfg) => (
                  <option key={cfg.study_name} value={cfg.study_name}>
                    {cfg.study_name} — {cfg.n_engines} engines ({cfg.fingerprint.slice(0, 8)}...)
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="flex items-center gap-2 text-xs">
            <input
              type="text"
              placeholder="Paste full path to .mmx file"
              value={mmxPath}
              onChange={(e) => setMmxPath(e.target.value)}
              className="flex-1 bg-background border border-border rounded px-2 py-1 text-xs font-mono"
            />
            <Button
              size="sm"
              variant="outline"
              disabled={!mmxPath.trim() || mmxUploading}
              onClick={handleMmxUpload}
              className="text-xs h-6 px-2"
            >
              {mmxUploading ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                "Upload"
              )}
            </Button>
            <label className="text-xs text-muted-foreground whitespace-nowrap">
              or
              <input
                type="file"
                accept=".mmx"
                onChange={handleMmxFile}
                disabled={mmxUploading}
                className="hidden"
              />
              <span className="ml-1 underline cursor-pointer hover:text-foreground">
                choose file…
              </span>
            </label>
          </div>

          <div className="text-[11px] text-muted-foreground">
            {effectiveStudyName
              ? `MMX will be stored as "${effectiveStudyName}".`
              : "Select or name a study first, or the MMX is stored as \"uploaded\" and not attached to anything."}
          </div>
        </div>

        {mmxError && (
          <div className="text-xs text-red-400 bg-red-500/10 rounded px-2 py-1">
            {mmxError}
          </div>
        )}
      </div>
    );
  },
);
