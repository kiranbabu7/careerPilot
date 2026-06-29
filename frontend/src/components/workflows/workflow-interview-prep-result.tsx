"use client";

import Link from "next/link";
import { ClipboardList, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { WorkflowDetail } from "@/lib/api";
import { interviewPrepNextAction } from "@/lib/workflow-utils";

interface WorkflowInterviewPrepResultProps {
  detail: WorkflowDetail;
  onViewPlan: () => void;
}

export function WorkflowInterviewPrepResult({
  detail,
  onViewPlan,
}: WorkflowInterviewPrepResultProps) {
  if (!detail.interview_plan_id) {
    return null;
  }

  const summary =
    interviewPrepNextAction(detail) ||
    detail.next_action ||
    "Interview prep plan generated — open it to review your roadmap and practice questions.";

  return (
    <Card className="border-primary/30 bg-primary/5">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="h-4 w-4 text-primary" />
          Interview prep ready
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">{summary}</p>
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" onClick={onViewPlan}>
            <ClipboardList className="h-4 w-4" />
            View prep plan
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link href={`/interviews?selected=${detail.interview_plan_id}`}>
              Open in Interviews
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
