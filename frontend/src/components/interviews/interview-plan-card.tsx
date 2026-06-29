"use client";

import Link from "next/link";
import { Building2, Calendar, MessageSquare } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { InterviewPlanSummary } from "@/lib/api";

interface InterviewPlanCardProps {
  plan: InterviewPlanSummary;
  onSelect: (id: string) => void;
}

export function InterviewPlanCard({ plan, onSelect }: InterviewPlanCardProps) {
  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={() => onSelect(plan.id)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(plan.id);
        }
      }}
      className="cursor-pointer transition-colors hover:border-primary/40 hover:shadow-sm"
    >
      <CardHeader className="space-y-1 p-4 pb-2">
        <CardTitle className="text-base font-semibold">{plan.job_title}</CardTitle>
        <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <Building2 className="h-3.5 w-3.5" />
          {plan.job_company}
        </p>
      </CardHeader>
      <CardContent className="space-y-2 p-4 pt-0 text-xs text-muted-foreground">
        <p className="flex items-center gap-1">
          <Calendar className="h-3 w-3" />
          {new Date(plan.created_at).toLocaleDateString()}
        </p>
        <p className="flex items-center gap-1">
          <MessageSquare className="h-3 w-3" />
          Prep plan · {plan.model_name}
          {plan.application_stage ? ` · ${plan.application_stage}` : ""}
        </p>
        {plan.application_id ? (
          <Link
            href={`/applications`}
            className="text-primary hover:underline"
            onClick={(event) => event.stopPropagation()}
          >
            View application
          </Link>
        ) : null}
      </CardContent>
    </Card>
  );
}
