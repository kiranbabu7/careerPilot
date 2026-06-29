"use client";

import Link from "next/link";
import { useState } from "react";
import { Download, Loader2, Play, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { WorkflowActionCard } from "@/lib/api";
import {
  downloadMaterialPdfById,
  MATERIAL_DOWNLOAD_ACTION_KEYS,
  MATERIAL_VIEW_ACTION_KEYS,
} from "@/components/workflows/workflow-material-utils";

interface WorkflowActionCardProps {
  action: WorkflowActionCard;
  disabled?: boolean;
  running?: boolean;
  onConfirm: (action: WorkflowActionCard) => void;
  onViewInterviewPlan?: (planId: string) => void;
  onViewMaterial?: (materialId: string) => void;
}

export function WorkflowActionCardButton({
  action,
  disabled = false,
  running = false,
  onConfirm,
  onViewInterviewPlan,
  onViewMaterial,
}: WorkflowActionCardProps) {
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const planId =
    typeof action.params?.interview_plan_id === "string"
      ? action.params.interview_plan_id
      : null;
  const materialId =
    typeof action.params?.material_id === "string" ? action.params.material_id : null;

  const isInterviewViewLink =
    Boolean(action.href) || (action.key === "view_interview_prep" && Boolean(planId));

  if (isInterviewViewLink && (action.href || planId)) {
    return (
      <Card className="border-emerald-500/30 bg-emerald-500/5">
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium">{action.label}</p>
            <p className="text-xs text-muted-foreground">{action.description}</p>
          </div>
          {onViewInterviewPlan && planId ? (
            <Button
              type="button"
              size="sm"
              disabled={disabled}
              onClick={() => onViewInterviewPlan(planId)}
              className="shrink-0"
            >
              <Sparkles className="h-4 w-4" />
              {action.label}
            </Button>
          ) : (
            <Button asChild size="sm" className="shrink-0">
              <Link href={action.href ?? `/interviews?selected=${planId}`}>
                <Sparkles className="h-4 w-4" />
                {action.label}
              </Link>
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  if (MATERIAL_VIEW_ACTION_KEYS.has(action.key) && materialId) {
    return (
      <Card className="border-emerald-500/30 bg-emerald-500/5">
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium">{action.label}</p>
            <p className="text-xs text-muted-foreground">{action.description}</p>
          </div>
          <Button
            type="button"
            size="sm"
            disabled={disabled}
            onClick={() => onViewMaterial?.(materialId)}
            className="shrink-0"
          >
            <Sparkles className="h-4 w-4" />
            {action.label}
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (MATERIAL_DOWNLOAD_ACTION_KEYS.has(action.key) && materialId) {
    return (
      <Card className="border-emerald-500/30 bg-emerald-500/5">
        <CardContent className="flex flex-col gap-3 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <p className="text-sm font-medium">{action.label}</p>
              <p className="text-xs text-muted-foreground">{action.description}</p>
            </div>
            <Button
              type="button"
              size="sm"
              disabled={disabled || downloading}
              onClick={() => {
                setDownloadError(null);
                setDownloading(true);
                void downloadMaterialPdfById(materialId)
                  .catch(() => setDownloadError("Download failed. Try again from mission control."))
                  .finally(() => setDownloading(false));
              }}
              className="shrink-0"
            >
              {downloading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              {downloading ? "Downloading..." : action.label}
            </Button>
          </div>
          {downloadError ? <p className="text-xs text-destructive">{downloadError}</p> : null}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-primary/20 bg-primary/5">
      <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <p className="text-sm font-medium">{action.label}</p>
          <p className="text-xs text-muted-foreground">{action.description}</p>
        </div>
        <Button
          type="button"
          size="sm"
          disabled={disabled || running}
          onClick={() => onConfirm(action)}
          className="shrink-0"
        >
          {running ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          {running
            ? "Running..."
            : action.requires_confirmation
              ? "Confirm & run"
              : "Run"}
        </Button>
      </CardContent>
    </Card>
  );
}
