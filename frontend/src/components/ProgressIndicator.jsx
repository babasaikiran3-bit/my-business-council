import { Card, CardContent } from "@/components/ui/card";
import { Loader2, CheckCircle2, XCircle, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Format elapsed time in seconds with 1 decimal place
 */
function formatTime(ms) {
  if (!ms || ms <= 0) return "0.0s";
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Get display name for a model (truncate long model names)
 */
function getModelDisplayName(model) {
  // Remove provider prefix for cleaner display
  const parts = model.split("/");
  return parts.length > 1 ? parts[1] : model;
}

/**
 * Individual model status indicator
 */
function ModelStatus({ model, status }) {
  const displayName = getModelDisplayName(model);

  return (
    <div className="flex items-center gap-2 text-sm">
      {status === "processing" && (
        <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
      )}
      {status === "received" && (
        <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
      )}
      {status === "failed" && (
        <XCircle className="h-3.5 w-3.5 text-red-500" />
      )}
      <span
        className={cn(
          "font-mono text-xs",
          status === "processing" && "text-muted-foreground",
          status === "received" && "text-foreground",
          status === "failed" && "text-red-500"
        )}
      >
        {displayName}
      </span>
      <span
        className={cn(
          "text-xs",
          status === "processing" && "text-muted-foreground",
          status === "received" && "text-green-600",
          status === "failed" && "text-red-500"
        )}
      >
        {status === "processing" && "Processing..."}
        {status === "received" && "✓ Received"}
        {status === "failed" && "✗ Failed"}
      </span>
    </div>
  );
}

/**
 * Stage 1 progress indicator with individual model statuses
 */
export function Stage1Progress({ modelStatuses, timing }) {
  const models = Object.keys(modelStatuses);
  const receivedCount = Object.values(modelStatuses).filter(
    (s) => s === "received"
  ).length;
  const failedCount = Object.values(modelStatuses).filter(
    (s) => s === "failed"
  ).length;
  const totalCount = models.length;

  const timeDisplay = timing.completed
    ? `Completed in ${formatTime(timing.elapsed)}`
    : formatTime(timing.elapsed);

  return (
    <Card className="border-dashed">
      <CardContent className="pt-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {timing.completed ? (
              <CheckCircle2 className="h-4 w-4 text-green-500" />
            ) : (
              <Loader2 className="h-4 w-4 animate-spin" />
            )}
            <span className="text-sm font-medium">
              Stage 1: Collecting responses
            </span>
            <span className="text-xs text-muted-foreground">
              ({receivedCount + failedCount}/{totalCount} models)
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Clock className="h-3.5 w-3.5" />
            <span className="font-mono">{timeDisplay}</span>
          </div>
        </div>

        {/* Model status grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 pl-7">
          {models.map((model) => (
            <ModelStatus
              key={model}
              model={model}
              status={modelStatuses[model]}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Get stage-specific styling
 */
function getStageStyle(stage) {
  switch (stage) {
    case 2:
      return {
        iconColor: "text-blue-500",
        completedColor: "text-blue-500",
      };
    case 3:
      return {
        iconColor: "text-purple-500",
        completedColor: "text-purple-500",
      };
    default:
      return {
        iconColor: "text-muted-foreground",
        completedColor: "text-green-500",
      };
  }
}

/**
 * Generic stage loading indicator with timer
 */
export function StageProgress({ stage, label, timing }) {
  const timeDisplay = timing.completed
    ? `Completed in ${formatTime(timing.elapsed)}`
    : formatTime(timing.elapsed);

  const stageStyle = getStageStyle(stage);

  return (
    <Card className="border-dashed">
      <CardContent className="pt-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {timing.completed ? (
              <CheckCircle2 className={cn("h-4 w-4", stageStyle.completedColor)} />
            ) : (
              <Loader2 className={cn("h-4 w-4 animate-spin", stageStyle.iconColor)} />
            )}
            <span className={cn(
              "text-sm",
              timing.completed ? "font-medium" : "text-muted-foreground"
            )}>
              {label}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Clock className="h-3.5 w-3.5" />
            <span className="font-mono">{timeDisplay}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

