"use client";

import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  workflowApi,
  type WorkflowDetail,
  type WorkflowTimelineItem,
} from "@/lib/api";
import { isWorkflowActive, POLL_INTERVAL_MS } from "@/lib/workflow-utils";

export function useWorkflowPolling(workflowId: string | null) {
  const [workflowDetail, setWorkflowDetail] = useState<WorkflowDetail | null>(null);
  const [timelineItems, setTimelineItems] = useState<WorkflowTimelineItem[]>([]);
  const [initialLoading, setInitialLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchWorkflow = useCallback(async () => {
    if (!workflowId) return null;

    const [detail, timelineResult] = await Promise.all([
      workflowApi.get(workflowId),
      workflowApi.timeline(workflowId).catch(() => null),
    ]);

    setWorkflowDetail(detail);
    setError(null);
    if (timelineResult) {
      setTimelineItems(timelineResult.items);
    } else {
      setTimelineItems([]);
    }

    return detail;
  }, [workflowId]);

  useEffect(() => {
    if (!workflowId) {
      setWorkflowDetail(null);
      setTimelineItems([]);
      setInitialLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setInitialLoading(true);

    void fetchWorkflow()
      .catch((err) => {
        if (cancelled) return;
        setError(
          err instanceof ApiError ? err.message : "Failed to load workflow status",
        );
      })
      .finally(() => {
        if (!cancelled) {
          setInitialLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [workflowId, fetchWorkflow]);

  const workflowStatus = workflowDetail?.workflow.status;
  const isPolling = Boolean(
    workflowId && workflowStatus && isWorkflowActive(workflowStatus),
  );

  useEffect(() => {
    if (!isPolling || !workflowId) {
      return;
    }

    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      try {
        await fetchWorkflow();
        if (!cancelled) {
          timeoutId = setTimeout(() => void poll(), POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof ApiError ? err.message : "Failed to load workflow status",
        );
      }
    };

    timeoutId = setTimeout(() => void poll(), POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [isPolling, workflowId, fetchWorkflow]);

  const refetch = useCallback(async () => {
    return fetchWorkflow();
  }, [fetchWorkflow]);

  return {
    workflowDetail,
    timelineItems,
    initialLoading,
    error,
    isPolling,
    workflowStatus,
    refetch,
  };
}
