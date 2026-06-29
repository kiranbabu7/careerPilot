"use client";

import { Calendar, Sparkles } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DecisionRecommendation } from "@/lib/api";
import { cn } from "@/lib/utils";

interface DecisionCardProps {
  recommendation: DecisionRecommendation;
  selected?: boolean;
  onSelect: (id: string) => void;
}

export function DecisionCard({ recommendation, selected, onSelect }: DecisionCardProps) {
  const actionCount =
    recommendation.action_count ?? recommendation.actions?.length ?? 0;

  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={() => onSelect(recommendation.id)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(recommendation.id);
        }
      }}
      className={cn(
        "cursor-pointer transition-colors hover:border-primary/40 hover:shadow-sm",
        selected && "border-primary/50 bg-primary/5",
      )}
    >
      <CardHeader className="space-y-1 p-4 pb-2">
        <CardTitle className="line-clamp-2 text-base font-semibold">
          {recommendation.summary}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 p-4 pt-0 text-xs text-muted-foreground">
        <p className="flex items-center gap-1">
          <Calendar className="h-3 w-3" />
          {new Date(recommendation.created_at).toLocaleString()}
        </p>
        <p className="flex items-center gap-1">
          <Sparkles className="h-3 w-3" />
          {recommendation.model_name}
          {actionCount > 0 ? ` · ${actionCount} action${actionCount === 1 ? "" : "s"}` : ""}
        </p>
      </CardContent>
    </Card>
  );
}
