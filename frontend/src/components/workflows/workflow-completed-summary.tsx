"use client";

import Link from "next/link";
import { Briefcase, CheckCircle2, ClipboardList, FileText, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { WorkflowDetail } from "@/lib/api";
import {
  isJobDiscoveryIntent,
  interviewPrepNextAction,
  jobDiscoveryCompletionMessage,
  resolveWorkflowIntent,
  suggestedNextStepLabels,
} from "@/lib/workflow-utils";

interface WorkflowCompletedSummaryProps {
  workflowId: string;
  detail: WorkflowDetail;
}

export function WorkflowCompletedSummary({
  workflowId,
  detail,
}: WorkflowCompletedSummaryProps) {
  const intent = resolveWorkflowIntent(detail);
  const guided = !isJobDiscoveryIntent(intent);
  const { accepted_count, evaluated_count, discovered_count, top_match_score } = detail;
  const scopedRoleCount =
    accepted_count > 0 ? accepted_count : evaluated_count > 0 ? evaluated_count : discovered_count;
  const hasScopedRoles = scopedRoleCount > 0;

  const completionMessage = guided
    ? detail.tailored_material_id
      ? detail.next_action || "Tailored resume generated — review and download below."
      : detail.interview_plan_id
        ? interviewPrepNextAction(detail) ||
          "Interview prep plan generated — review your practice plan below."
      : detail.next_action ||
        (intent === "tailor_resume"
          ? "Plan ready — select a role below to tailor your resume."
          : intent === "cover_letter"
            ? "Plan ready — pick an opportunity for your cover letter."
            : intent === "interview_prep"
              ? "Generating interview prep plan..."
              : "Plan ready — review your application pipeline.")
    : jobDiscoveryCompletionMessage(detail);

  const nextStepLabels = suggestedNextStepLabels(detail);

  return (
    <Card className="border-emerald-500/30 bg-emerald-500/5">
      <CardContent className="space-y-4 p-5">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-emerald-500/15 text-emerald-500">
            <CheckCircle2 className="h-5 w-5" />
          </div>
          <div className="space-y-1">
            <p className="font-medium">Mission complete</p>
            <p className="text-sm text-muted-foreground">
              {completionMessage}
              {!guided && top_match_score > 0 ? ` (top score ${top_match_score}/100)` : ""}
            </p>
          </div>
        </div>

        {nextStepLabels.length > 0 ? (
          <div className="space-y-2">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Suggested next steps
            </p>
            <div className="flex flex-wrap gap-2">
              {nextStepLabels.map((label) => (
                <span
                  key={label}
                  className="rounded-lg border border-border bg-muted/30 px-3 py-1.5 text-sm text-muted-foreground"
                >
                  {label}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          {guided ? (
            <>
              {(intent === "tailor_resume" || intent === "cover_letter") &&
              intent === "cover_letter" ? (
                <Button asChild size="sm">
                  <Link href="/opportunities">
                    <Briefcase className="h-4 w-4" />
                    Pick opportunity
                  </Link>
                </Button>
              ) : null}
              {intent === "tailor_resume" && !detail.tailored_material_id ? (
                <Button asChild variant="outline" size="sm">
                  <Link href="/resume">
                    <FileText className="h-4 w-4" />
                    Resume workspace
                  </Link>
                </Button>
              ) : null}
              {detail.interview_plan_id ? (
                <Button asChild size="sm">
                  <Link href={`/interviews?selected=${detail.interview_plan_id}`}>
                    <Sparkles className="h-4 w-4" />
                    View prep plan
                  </Link>
                </Button>
              ) : intent === "interview_prep" ? (
                <Button asChild size="sm">
                  <Link href="/interviews">
                    <Sparkles className="h-4 w-4" />
                    Interview prep
                  </Link>
                </Button>
              ) : null}
              {(intent === "application_tracking" ||
                intent === "interview_prep" ||
                detail.interview_plan_id) && (
                <Button asChild variant="outline" size="sm">
                  <Link href="/applications">
                    <ClipboardList className="h-4 w-4" />
                    Applications
                  </Link>
                </Button>
              )}
            </>
          ) : accepted_count > 0 ? (
            <Button asChild size="sm">
              <Link
                href={`/opportunities?workflow_id=${workflowId}&filter=high_match`}
              >
                <Briefcase className="h-4 w-4" />
                View {accepted_count} match{accepted_count === 1 ? "" : "es"}
              </Link>
            </Button>
          ) : hasScopedRoles ? (
            <Button asChild size="sm">
              <Link
                href={`/opportunities?workflow_id=${workflowId}&filter=all`}
              >
                <Briefcase className="h-4 w-4" />
                View {scopedRoleCount} role{scopedRoleCount === 1 ? "" : "s"}
              </Link>
            </Button>
          ) : (
            <Button asChild variant="outline" size="sm">
              <Link href="/opportunities">
                <Briefcase className="h-4 w-4" />
                Browse opportunities
              </Link>
            </Button>
          )}
          <Button asChild variant="outline" size="sm">
            <Link href={`/agent-runs?workflow_id=${workflowId}`}>
              <Sparkles className="h-4 w-4" />
              Agent runs
            </Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link href="/applications">
              <ClipboardList className="h-4 w-4" />
              Applications
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
