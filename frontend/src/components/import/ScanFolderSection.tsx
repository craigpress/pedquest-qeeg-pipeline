import { Loader2, FolderSearch, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Props {
  folderPath: string;
  onFolderPathChange: (v: string) => void;
  scanning: boolean;
  scanProgress: { classified: number; total: number } | null;
  scanError: string | null;
  onScan: () => void;
  onDismissError: () => void;
}

export function ScanFolderSection({
  folderPath,
  onFolderPathChange,
  scanning,
  scanProgress,
  scanError,
  onScan,
  onDismissError,
}: Props) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Scan Folder</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">
          Point to a study folder — all Persyst CSVs, clinical data, and corrections will be
          detected and grouped by patient automatically.
        </p>
        <div className="flex gap-2">
          <Input
            value={folderPath}
            onChange={(e) => onFolderPathChange(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") onScan(); }}
            placeholder="C:\path\to\study\folder"
            className="flex-1 h-8 text-xs font-mono"
          />
          <Button
            size="sm"
            className="h-8 text-xs gap-1.5"
            onClick={onScan}
            disabled={!folderPath.trim() || scanning}
          >
            {scanning ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <FolderSearch className="h-3 w-3" />
            )}
            {scanning ? "Scanning..." : "Scan"}
          </Button>
        </div>
        {scanProgress && (
          <p className="text-xs text-muted-foreground">
            Scanning… {scanProgress.classified} / {scanProgress.total} files
          </p>
        )}
        {scanError && (
          <div className="flex items-center gap-2 p-2 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
            <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
            <span>{scanError}</span>
            <Button
              variant="ghost"
              size="sm"
              className="ml-auto h-6 text-[10px]"
              onClick={onDismissError}
            >
              Dismiss
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
