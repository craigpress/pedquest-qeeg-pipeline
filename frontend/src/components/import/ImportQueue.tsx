import { FileText, Loader2, CheckCircle, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export interface FileEntry {
  upload: { file_id: string; filename: string; patient_id: string; size_bytes: number };
  status: "uploaded" | "processing" | "complete" | "error";
  progress: number;
  message: string;
}

interface Props {
  files: FileEntry[];
  onProcessAll: () => void;
  onViewPatients: () => void;
}

export function ImportQueue({ files, onProcessAll, onViewPatients }: Props) {
  if (files.length === 0) return null;

  const readyCount = files.filter((f) => f.status === "uploaded").length;
  const hasComplete = files.some((f) => f.status === "complete");

  return (
    <>
      {readyCount > 0 && (
        <Button onClick={onProcessAll} className="w-full" size="lg">
          Process {readyCount} File{readyCount !== 1 ? "s" : ""}
        </Button>
      )}

      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm">Processing Queue</CardTitle>
            {hasComplete && (
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                onClick={onViewPatients}
              >
                View Patient List
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {files.map((f) => (
            <div
              key={f.upload.file_id}
              className="flex items-center gap-3 p-2 rounded bg-muted/30"
            >
              <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-mono truncate">{f.upload.filename}</p>
                <p className="text-[10px] text-muted-foreground">{f.message}</p>
                {f.status === "processing" && (
                  <div className="mt-1 h-1 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary transition-all"
                      style={{ width: `${f.progress * 100}%` }}
                    />
                  </div>
                )}
              </div>
              <div className="flex-shrink-0">
                {f.status === "uploaded" && (
                  <Badge variant="outline" className="text-[9px]">Ready</Badge>
                )}
                {f.status === "processing" && (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-500" />
                )}
                {f.status === "complete" && (
                  <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
                )}
                {f.status === "error" && (
                  <AlertCircle className="h-3.5 w-3.5 text-red-500" />
                )}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </>
  );
}
