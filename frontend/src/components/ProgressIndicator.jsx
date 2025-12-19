import { useState, useEffect, useRef } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, CheckCircle2, XCircle, Clock, Square } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Format elapsed time in seconds with 1 decimal place
 */
function formatTime(ms) {
  if (!ms || ms <= 0) return "0.0s";
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Self-updating timer component that owns its own interval.
 * This prevents parent components from needing to update state every 500ms
 * for timer display, reducing unnecessary re-renders.
 *
 * @param {Object} props
 * @param {number} props.startTime - Unix timestamp when the timer started
 * @param {boolean} props.completed - Whether the stage is completed
 * @param {number} [props.finalElapsed] - Final elapsed time (used when completed)
 * @param {number} [props.updateInterval=500] - How often to update the display (ms)
 */
export function StageTimer({ startTime, completed, finalElapsed, updateInterval = 500 }) {
  const [elapsed, setElapsed] = useState(() => {
    if (completed && finalElapsed != null) return finalElapsed;
    if (startTime) return Date.now() - startTime;
    return 0;
  });
  const intervalRef = useRef(null);

  useEffect(() => {
    // If completed, use the final elapsed time and don't start interval
    if (completed) {
      if (finalElapsed != null) {
        setElapsed(finalElapsed);
      }
      return;
    }

    // If not started yet, nothing to do
    if (!startTime) {
      setElapsed(0);
      return;
    }

    // Start the interval for live updates
    intervalRef.current = setInterval(() => {
      setElapsed(Date.now() - startTime);
    }, updateInterval);

    // Initial update
    setElapsed(Date.now() - startTime);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [startTime, completed, finalElapsed, updateInterval]);

  const timeDisplay = completed
    ? `Completed in ${formatTime(elapsed)}`
    : formatTime(elapsed);

  return (
    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <Clock className="h-3.5 w-3.5" />
      <span className="font-mono">{timeDisplay}</span>
    </div>
  );
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
 * Stage 1 progress indicator with individual model statuses.
 * Uses StageTimer for self-updating elapsed time display.
 */
export function Stage1Progress({ modelStatuses, timing, onCancel }) {
  const models = Object.keys(modelStatuses);
  const receivedCount = Object.values(modelStatuses).filter(
    (s) => s === "received"
  ).length;
  const failedCount = Object.values(modelStatuses).filter(
    (s) => s === "failed"
  ).length;
  const processingCount = Object.values(modelStatuses).filter(
    (s) => s === "processing"
  ).length;
  const totalCount = models.length;
  const completedCount = receivedCount + failedCount;

  // Determine the status summary text and styling
  const getStatusSummary = () => {
    if (timing.completed) {
      if (failedCount === 0) {
        return { text: `${receivedCount}/${totalCount} succeeded`, className: "text-green-600" };
      } else if (receivedCount === 0) {
        return { text: `All ${totalCount} models failed`, className: "text-red-500" };
      } else {
        return { text: `${receivedCount} succeeded, ${failedCount} failed`, className: "text-amber-600" };
      }
    } else {
      return { text: `${completedCount}/${totalCount} models`, className: "text-muted-foreground" };
    }
  };

  const statusSummary = getStatusSummary();

  return (
    <Card className="border-dashed">
      <CardContent className="pt-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {timing.completed ? (
              failedCount > 0 && receivedCount === 0 ? (
                <XCircle className="h-4 w-4 text-red-500" />
              ) : failedCount > 0 ? (
                <CheckCircle2 className="h-4 w-4 text-amber-500" />
              ) : (
                <CheckCircle2 className="h-4 w-4 text-green-500" />
              )
            ) : (
              <Loader2 className="h-4 w-4 animate-spin" />
            )}
            <span className="text-sm font-medium">
              Stage 1: Collecting responses
            </span>
            <span className={cn("text-xs", statusSummary.className)}>
              ({statusSummary.text})
            </span>
          </div>
          <div className="flex items-center gap-2">
            <StageTimer
              startTime={timing.startTime}
              completed={timing.completed}
              finalElapsed={timing.elapsed}
            />
            {!timing.completed && onCancel && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onCancel}
                className="h-6 px-2 text-destructive hover:text-destructive hover:bg-destructive/10"
              >
                <Square className="h-3 w-3 fill-current" />
              </Button>
            )}
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
 * Generic stage loading indicator with timer.
 * Uses StageTimer for self-updating elapsed time display.
 */
export function StageProgress({ stage, label, timing, onCancel }) {
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
          <div className="flex items-center gap-2">
            <StageTimer
              startTime={timing.startTime}
              completed={timing.completed}
              finalElapsed={timing.elapsed}
            />
            {!timing.completed && onCancel && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onCancel}
                className="h-6 px-2 text-destructive hover:text-destructive hover:bg-destructive/10"
              >
                <Square className="h-3 w-3 fill-current" />
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

