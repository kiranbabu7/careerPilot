"use client";



import Link from "next/link";

import { useCallback, useEffect, useRef, useState } from "react";

import { AlertCircle, Loader2, Radio } from "lucide-react";



import { InterviewPlanDetail } from "@/components/interviews/interview-plan-detail";

import { AgentPipeline } from "@/components/workflows/agent-pipeline";

import { WorkflowChat } from "@/components/workflows/workflow-chat";

import { WorkflowCompletedSummary } from "@/components/workflows/workflow-completed-summary";
import { WorkflowDiscoveryMatches } from "@/components/workflows/workflow-discovery-matches";
import { WorkflowRejectedRoles } from "@/components/workflows/workflow-rejected-roles";
import { WorkflowToolProgressFeed } from "@/components/workflows/workflow-tool-progress-feed";

import { WorkflowInterviewPrepResult } from "@/components/workflows/workflow-interview-prep-result";
import { WorkflowIntentCallout } from "@/components/workflows/workflow-intent-callout";

import { Button } from "@/components/ui/button";

import { Card, CardContent } from "@/components/ui/card";

import type { AgentExecution, WorkflowDetail } from "@/lib/api";

import {

  buildPipelineSteps,

  isSearchRerunActive,

  resolveActiveCoverLetterMaterialId,

  resolveActiveTailoredMaterialId,

  resolveIntentClassification,

  resolvePlannedAgents,

  workflowRefinementFlags,

} from "@/lib/workflow-utils";

import { scrollToElementInScrollArea } from "@/components/workflows/workflow-material-utils";

import { cn } from "@/lib/utils";



interface WorkflowMissionControlProps {

  workflowId: string;

  detail: WorkflowDetail | null;

  agentRuns?: AgentExecution[];

  initialLoading: boolean;

  error: string | null;

  isPolling: boolean;

  onViewRun?: (executionId: string) => void;

  onWorkflowUpdated?: () => void | Promise<void>;

  className?: string;

}



function WorkflowInlineContent({

  isPolling,

  workflowCompleted,

  workflowFailed,

  detail,

  plannedAgents,

  steps,

  intentClassification,

  jobDiscovery,

  pinnedTailoredMaterialId,

  pinnedCoverLetterMaterialId,

  searchRerunActive,

  hasInterviewPlan,

  workflowId,

  onWorkflowUpdated,

  onViewInterviewPlan,

  error,

}: {

  isPolling: boolean;

  workflowCompleted: boolean;

  workflowFailed: boolean;

  detail: WorkflowDetail | null;

  plannedAgents: string[];

  steps: ReturnType<typeof buildPipelineSteps>;

  intentClassification: ReturnType<typeof resolveIntentClassification>;

  jobDiscovery: boolean;

  pinnedTailoredMaterialId: string | null;

  pinnedCoverLetterMaterialId: string | null;

  searchRerunActive: boolean;

  hasInterviewPlan: boolean;

  workflowId: string;

  onWorkflowUpdated?: () => void | Promise<void>;

  onViewInterviewPlan: () => void;

  error: string | null;

}) {

  const { includeRejected } = workflowRefinementFlags(detail);

  return (

    <>

      <div className="rounded-lg border border-border/60 bg-muted/30 px-3 py-2">

        <div className="flex flex-wrap items-center gap-2">

          <div className="flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">

            {isPolling ? (

              <>

                <Radio className="h-3 w-3 animate-pulse" />

                Live

              </>

            ) : workflowCompleted && !searchRerunActive && !isPolling ? (

              "Completed"

            ) : workflowFailed ? (

              "Failed"

            ) : (

              "Workflow"

            )}

          </div>

          {isPolling ? (

            <span className="text-xs text-muted-foreground">Agents update every few seconds</span>

          ) : null}

          {plannedAgents.length > 0 ? (

            <span className="text-xs text-muted-foreground">

              {plannedAgents.join(" → ")}

            </span>

          ) : null}

        </div>

        {detail?.plan_summary && !isPolling ? (

          <p className="mt-2 text-sm text-muted-foreground">{detail.plan_summary}</p>

        ) : null}

        {detail?.user_visible_plan &&
        typeof detail.user_visible_plan === "string" &&
        detail.user_visible_plan.trim() ? (
          <p className="mt-1 text-xs text-muted-foreground">{detail.user_visible_plan}</p>
        ) : null}

      </div>

      {isPolling ? <WorkflowToolProgressFeed detail={detail} /> : null}

      {intentClassification ? (
        <WorkflowIntentCallout classification={intentClassification} detail={detail} />
      ) : null}



      <div className="space-y-2">

        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">

          Agent pipeline

        </p>

        <AgentPipeline steps={steps} compact />

      </div>



      {detail && jobDiscovery && !searchRerunActive && !isPolling && (detail.discovered_count > 0 || detail.evaluated_count > 0 || detail.accepted_count > 0) ? (
        <WorkflowDiscoveryMatches
          workflowId={workflowId}
          discoveredCount={detail.discovered_count}
          evaluatedCount={detail.evaluated_count}
          acceptedCount={detail.accepted_count}
        />
      ) : detail?.next_action &&
        !jobDiscovery &&
        !pinnedTailoredMaterialId &&
        !pinnedCoverLetterMaterialId &&
        !hasInterviewPlan ? (

        <Card className="border-primary/30 bg-primary/5">

          <CardContent className="p-3">

            <p className="text-sm font-medium">What&apos;s next</p>

            <p className="text-sm text-muted-foreground">{detail.next_action}</p>

          </CardContent>

        </Card>

      ) : null}



      {detail && jobDiscovery && detail.rejected_count > 0 && includeRejected ? (
        <WorkflowRejectedRoles
          workflowId={workflowId}
          rejectedCount={detail.rejected_count}
          defaultExpanded
        />
      ) : null}



      {detail && hasInterviewPlan && !searchRerunActive ? (

        <WorkflowInterviewPrepResult detail={detail} onViewPlan={onViewInterviewPlan} />

      ) : null}



      {workflowFailed ? (

        <Card className="border-destructive/30 bg-destructive/5">

          <CardContent className="p-3">

            <p className="text-sm font-medium text-destructive">Workflow failed</p>

            <p className="text-sm text-muted-foreground">

              {detail?.workflow.error_message || "An unexpected error occurred."}

            </p>

          </CardContent>

        </Card>

      ) : null}



      {workflowCompleted && detail && !searchRerunActive && !isPolling ? (

        <WorkflowCompletedSummary workflowId={workflowId} detail={detail} />

      ) : null}



      {error && detail ? <p className="text-sm text-destructive">{error}</p> : null}

    </>

  );

}



export function WorkflowMissionControl({

  workflowId,

  detail,

  initialLoading,

  error,

  isPolling,

  onWorkflowUpdated,

  className,

}: WorkflowMissionControlProps) {

  const [interviewPlanPanelOpen, setInterviewPlanPanelOpen] = useState(false);

  const [activeInterviewPlanId, setActiveInterviewPlanId] = useState<string | null>(null);

  const [highlightedMaterialId, setHighlightedMaterialId] = useState<string | null>(null);

  const previousInterviewPlanIdRef = useRef<string | null>(null);



  const workflowStatus = detail?.workflow.status;

  const workflowFailed = workflowStatus === "failed";

  const workflowCompleted = workflowStatus === "completed";

  const hasInterviewPlan = Boolean(detail?.interview_plan_id);

  const searchRerunActive = isSearchRerunActive(detail);
  const pinnedTailoredMaterialId = resolveActiveTailoredMaterialId(detail);
  const pinnedCoverLetterMaterialId = resolveActiveCoverLetterMaterialId(detail);

  const plannedAgents = resolvePlannedAgents(detail);

  const jobDiscovery = plannedAgents.includes("job_search");

  const steps = buildPipelineSteps(detail, isPolling);

  const intentClassification = resolveIntentClassification(detail);

  const goal = detail?.workflow.goal ?? "Career workflow";



  const openInterviewPlan = useCallback(

    (planId?: string) => {

      const resolvedPlanId = planId ?? detail?.interview_plan_id ?? null;

      if (!resolvedPlanId) return;

      setActiveInterviewPlanId(resolvedPlanId);

      setInterviewPlanPanelOpen(true);

    },

    [detail?.interview_plan_id],

  );



  const scrollToMaterial = useCallback((materialId: string) => {

    setHighlightedMaterialId(materialId);

    const attemptScroll = () =>
      scrollToElementInScrollArea(
        document.getElementById(`workflow-material-${materialId}`),
      );

    requestAnimationFrame(() => {
      if (!attemptScroll()) {
        window.setTimeout(attemptScroll, 150);
      }
    });

  }, []);



  useEffect(() => {

    const planId = detail?.interview_plan_id ?? null;

    if (!planId || planId === previousInterviewPlanIdRef.current) {

      return;

    }

    previousInterviewPlanIdRef.current = planId;

    setActiveInterviewPlanId(planId);

    setInterviewPlanPanelOpen(true);

  }, [detail?.interview_plan_id]);



  if (initialLoading && !detail) {

    return (

      <div className="flex min-h-[320px] flex-col items-center justify-center gap-3 text-center">

        <Loader2 className="h-8 w-8 animate-spin text-primary" />

        <p className="text-sm font-medium">Connecting to mission control...</p>

        <p className="text-xs text-muted-foreground">Loading workflow status</p>

      </div>

    );

  }



  if (error && !detail) {

    return (

      <Card className="border-destructive/30 bg-destructive/5">

        <CardContent className="flex items-start gap-3 p-5">

          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />

          <div className="space-y-2">

            <p className="font-medium text-destructive">Failed to load workflow</p>

            <p className="text-sm text-muted-foreground">{error}</p>

            <Button asChild variant="outline" size="sm">

              <Link href="/">Start a new goal from Home</Link>

            </Button>

          </div>

        </CardContent>

      </Card>

    );

  }



  const chatSubtitle = isPolling

    ? "Agents running — refine results when complete"

    : workflowCompleted && !searchRerunActive

        ? "Ask about results or confirm follow-up actions"

        : workflowFailed

          ? "Workflow ended with errors"

          : "Workflow status and refinement";



  return (

    <div className={cn("flex h-full min-h-0 flex-col", className)}>

      <WorkflowChat

        workflowId={workflowId}

        detail={detail}

        disabled={isPolling}

        onWorkflowUpdated={onWorkflowUpdated}

        onViewInterviewPlan={openInterviewPlan}

        onViewMaterial={scrollToMaterial}

        highlightedMaterialId={highlightedMaterialId}

        className="min-h-0 flex-1"

        title={goal}

        subtitle={chatSubtitle}

        topContent={

          <WorkflowInlineContent

            isPolling={isPolling}

            workflowCompleted={workflowCompleted}

            workflowFailed={workflowFailed}

            detail={detail}

            plannedAgents={plannedAgents}

            steps={steps}

            intentClassification={intentClassification}

            jobDiscovery={jobDiscovery}

            pinnedTailoredMaterialId={pinnedTailoredMaterialId}

            pinnedCoverLetterMaterialId={pinnedCoverLetterMaterialId}

            searchRerunActive={searchRerunActive}

            hasInterviewPlan={hasInterviewPlan}

            workflowId={workflowId}

            onWorkflowUpdated={onWorkflowUpdated}

            onViewInterviewPlan={() => openInterviewPlan()}

            error={error}

          />

        }

      />



      {interviewPlanPanelOpen && activeInterviewPlanId ? (

        <InterviewPlanDetail

          planId={activeInterviewPlanId}

          onClose={() => setInterviewPlanPanelOpen(false)}

        />

      ) : null}

    </div>

  );

}

