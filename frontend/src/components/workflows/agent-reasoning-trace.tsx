"use client";

import { ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";

import type { ReasoningTraceEntry } from "@/lib/workflow-utils";
import { cn } from "@/lib/utils";

interface AgentReasoningTraceProps {
  entries: ReasoningTraceEntry[];
  compact?: boolean;
  className?: string;
}

const VARIANT_STYLES: Record<
  NonNullable<ReasoningTraceEntry["variant"]>,
  string
> = {
  default: "text-muted-foreground",
  constraint: "text-primary/90",
  replan: "text-amber-700 dark:text-amber-400",
  approval: "text-violet-700 dark:text-violet-300",
  skipped: "text-muted-foreground line-through decoration-muted-foreground/60",
};

function entryClassName(variant: ReasoningTraceEntry["variant"]): string {
  return VARIANT_STYLES[variant ?? "default"];
}

export function AgentReasoningTrace({
  entries,
  compact = false,
  className,
}: AgentReasoningTraceProps) {
  const [expanded, setExpanded] = useState(false);

  if (entries.length === 0) return null;

  return (
    <div className={cn("space-y-2", className)}>
      <button
        type="button"
        className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        aria-expanded={expanded}
        onClick={() => setExpanded((value) => !value)}
      >
        Why
        {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>
      {expanded ? (
        <ul
          className={cn(
            "space-y-1.5 rounded-lg border border-border/50 bg-background/40",
            compact ? "px-2.5 py-2 text-xs" : "px-3 py-2 text-sm",
          )}
        >
          {entries.map((entry, index) => (
            <li key={`${entry.label}-${index}`}>
              <span className="font-medium text-foreground">{entry.label}: </span>
              <span className={entryClassName(entry.variant)}>{entry.detail}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
