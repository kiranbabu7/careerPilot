"use client";

import { useEffect, useRef } from "react";
import {
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  Loader2,
  Search,
  Sparkles,
  XCircle,
} from "lucide-react";

import { AgentReasoningTrace } from "@/components/workflows/agent-reasoning-trace";
import type { PipelineStepInfo, PipelineStepState } from "@/lib/workflow-utils";
import { cn } from "@/lib/utils";

const STEP_ICONS: Record<string, typeof Sparkles> = {
  planner: Sparkles,
  job_search: Search,
  company_research: Search,
  job_evaluation: ClipboardCheck,
  guided_next: ArrowRight,
};

function StepStatusIcon({ state }: { state: PipelineStepState }) {
  if (state === "running") {
    return <Loader2 className="h-5 w-5 animate-spin text-primary" />;
  }
  if (state === "completed") {
    return <CheckCircle2 className="h-5 w-5 text-emerald-500" />;
  }
  if (state === "failed") {
    return <XCircle className="h-5 w-5 text-destructive" />;
  }
  return <div className="h-5 w-5 rounded-full border-2 border-muted-foreground/30" />;
}

interface AgentPipelineProps {
  steps: PipelineStepInfo[];
  compact?: boolean;
}

export function AgentPipeline({ steps, compact = false }: AgentPipelineProps) {
  const activeRef = useRef<HTMLDivElement>(null);
  const activeStepKey = steps.find((step) => step.isActive)?.key;

  useEffect(() => {
    activeRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [activeStepKey]);

  return (
    <div className="relative">
      {!compact ? (
        <div className="absolute left-6 top-8 hidden h-[calc(100%-4rem)] w-px bg-gradient-to-b from-primary/40 via-primary/20 to-transparent lg:hidden" />
      ) : null}

      <ol
        className={cn(
          compact ? "space-y-2" : "space-y-4 lg:flex lg:items-stretch lg:gap-0 lg:space-y-0",
        )}
      >
        {steps.map((step, index) => {
          const Icon = STEP_ICONS[step.key] ?? Sparkles;
          const isLast = index === steps.length - 1;

          return (
            <li
              key={step.key}
              className={cn("relative", compact ? "" : "flex-1", !isLast && !compact && "lg:pr-6")}
            >
              {!isLast && !compact ? (
                <div
                  className="absolute right-0 top-10 z-0 hidden h-px w-6 bg-gradient-to-r from-primary/40 to-primary/10 lg:block"
                  aria-hidden
                />
              ) : null}

              <div
                ref={step.isActive ? activeRef : undefined}
                className={cn(
                  "relative rounded-xl border bg-card/60 backdrop-blur transition-all duration-500",
                  compact ? "p-3" : "p-4",
                  step.isActive &&
                    "border-primary/50 shadow-[0_0_24px_-4px] shadow-primary/30 ring-1 ring-primary/20",
                  step.state === "completed" && !step.isActive && "border-emerald-500/20",
                  step.state === "failed" && "border-destructive/40",
                  step.state === "pending" && "border-border/60 opacity-80",
                  step.state === "idle" && "border-border/40 opacity-60",
                )}
              >
                {step.isActive && step.state === "running" ? (
                  <span className="absolute inset-0 animate-pulse rounded-xl bg-primary/5" />
                ) : null}

                <div className={cn("relative", compact ? "space-y-2" : "space-y-3")}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div
                        className={cn(
                          "flex shrink-0 items-center justify-center rounded-lg",
                          compact ? "h-8 w-8" : "h-10 w-10",
                          step.isActive ? "bg-primary/15 text-primary" : "bg-muted/50 text-muted-foreground",
                        )}
                      >
                        <Icon className={compact ? "h-4 w-4" : "h-5 w-5"} />
                      </div>
                      <div>
                        <p className={compact ? "text-sm font-medium" : "font-medium"}>{step.label}</p>
                        <p className="text-xs capitalize text-muted-foreground">{step.state}</p>
                      </div>
                    </div>
                    <StepStatusIcon state={step.state} />
                  </div>

                  {step.detail ? (
                    <p className={cn("text-muted-foreground", compact ? "text-xs" : "text-sm")}>
                      {step.detail}
                    </p>
                  ) : null}

                  {step.toolRationale ? (
                    <p
                      className={cn(
                        "rounded-lg border border-primary/20 bg-primary/5 text-foreground/90",
                        compact ? "px-2.5 py-1.5 text-xs" : "px-3 py-2 text-sm",
                      )}
                    >
                      <span className="font-medium">Why this tool: </span>
                      {step.toolRationale}
                    </p>
                  ) : null}

                  {step.summary ? (
                    <p
                      className={cn(
                        "rounded-lg border border-border/50 bg-background/40 text-muted-foreground",
                        compact ? "px-2.5 py-1.5 text-xs" : "px-3 py-2 text-sm",
                      )}
                    >
                      {step.summary}
                    </p>
                  ) : null}

                  {step.reasoningTrace && step.reasoningTrace.length > 0 ? (
                    <AgentReasoningTrace entries={step.reasoningTrace} compact={compact} />
                  ) : null}

                  {step.execution?.error_message ? (
                    <p className="text-sm text-destructive">{step.execution.error_message}</p>
                  ) : null}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
