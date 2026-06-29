"use client";



import { useCallback, useEffect, useMemo, useState } from "react";



import { ChatPanel, type ChatMessage, type QuickReply } from "@/components/chat/chat-panel";

import { WorkflowActionCardButton } from "@/components/workflows/workflow-action-card";
import { WorkflowChatOpportunityList } from "@/components/workflows/workflow-chat-opportunity-list";
import { WorkflowMaterialResult } from "@/components/workflows/workflow-material-result";
import { WorkflowTailorSelector } from "@/components/workflows/workflow-tailor-selector";

import {

  clearAllPendingActions,

  clearConsumedAction,

} from "@/components/workflows/workflow-chat-utils";

import {

  ApiError,

  workflowApi,

  type WorkflowActionCard,
  type WorkflowDetail,
  type WorkflowMessage,
} from "@/lib/api";
import {
  deriveWorkflowQuickReplies,
  parseWorkflowRefinementResult,
  resolveActiveCoverLetterMaterialId,
  resolveActiveTailoredMaterialId,
  resolveActiveTailorSelection,
  shouldRenderMaterialActionInFooter,
} from "@/lib/workflow-utils";



interface WorkflowChatProps {
  workflowId: string;
  detail?: WorkflowDetail | null;
  disabled?: boolean;
  onWorkflowUpdated?: () => Promise<void> | void;
  onViewInterviewPlan?: (planId: string) => void;
  onViewMaterial?: (materialId: string) => void;
  highlightedMaterialId?: string | null;
  className?: string;
  title?: string;
  subtitle?: string;
  topContent?: React.ReactNode;
}



function toChatMessages(messages: WorkflowMessage[]): ChatMessage[] {

  return messages

    .filter((message) => message.role !== "system")

    .map((message) => ({

      id: message.id,

      role: message.role === "user" ? "user" : "assistant",

      content: message.content,

    }));

}



export function WorkflowChat({

  workflowId,

  detail = null,

  disabled = false,

  onWorkflowUpdated,

  onViewInterviewPlan,

  onViewMaterial,

  highlightedMaterialId = null,

  className,

  title,

  subtitle,

  topContent,

}: WorkflowChatProps) {

  const [messages, setMessages] = useState<WorkflowMessage[]>([]);

  const [inputValue, setInputValue] = useState("");

  const [loading, setLoading] = useState(true);

  const [sending, setSending] = useState(false);

  const [runningAction, setRunningAction] = useState<{

    messageId: string;

    action: WorkflowActionCard;

  } | null>(null);

  const [error, setError] = useState<string | null>(null);



  const syncMessages = useCallback(async () => {

    const data = await workflowApi.messages(workflowId);

    setMessages(data.messages);

    return data.messages;

  }, [workflowId]);



  const loadMessages = useCallback(async () => {

    setLoading(true);

    try {

      await syncMessages();

      setError(null);

    } catch (err) {

      setError(err instanceof ApiError ? err.message : "Failed to load chat");

    } finally {

      setLoading(false);

    }

  }, [syncMessages]);



  useEffect(() => {

    void loadMessages();

  }, [loadMessages]);



  const chatMessages = useMemo(() => toChatMessages(messages), [messages]);

  const quickReplies = useMemo(
    () => deriveWorkflowQuickReplies(messages, detail),
    [messages, detail],
  );

  const messagesById = useMemo(

    () => new Map(messages.map((message) => [message.id, message])),

    [messages],

  );

  const activeTailorSelection = useMemo(
    () => resolveActiveTailorSelection(messages, detail),
    [messages, detail],
  );

  const activeTailoredMaterialId = useMemo(
    () => resolveActiveTailoredMaterialId(detail),
    [detail],
  );

  const activeCoverLetterMaterialId = useMemo(
    () => resolveActiveCoverLetterMaterialId(detail),
    [detail],
  );



  const handleSend = async (contentOverride?: string) => {

    const content = (contentOverride ?? inputValue).trim();

    if (!content || sending || disabled || runningAction) return;



    setSending(true);

    setError(null);

    try {

      const result = await workflowApi.postMessage(workflowId, content);

      setMessages((prev) => {

        const cleared = result.confirmed ? clearAllPendingActions(prev) : prev;

        const nextMessages: WorkflowMessage[] = [...cleared, result.user_message];

        if (result.system_message) {

          nextMessages.push(result.system_message);

        }

        nextMessages.push(result.assistant_message);

        return nextMessages;

      });

      setInputValue("");

      const viewPrepAction = result.assistant_message.actions?.find(
        (action) => action.key === "view_interview_prep",
      );
      const planId =
        typeof viewPrepAction?.params?.interview_plan_id === "string"
          ? viewPrepAction.params.interview_plan_id
          : null;
      if (planId) {
        onViewInterviewPlan?.(planId);
      }

      if (result.confirmed || result.workflow) {
        await onWorkflowUpdated?.();
        if (result.confirmed) {
          await syncMessages();
        }
      }

    } catch (err) {

      setError(err instanceof ApiError ? err.message : "Failed to send message");

    } finally {

      setSending(false);

    }

  };



  const handleQuickReply = (reply: QuickReply) => {

    void handleSend(reply.value);

  };



  const handleConfirmAction = async (messageId: string, action: WorkflowActionCard) => {

    if (runningAction || disabled) return;



    setRunningAction({ messageId, action });

    setMessages((prev) => clearConsumedAction(prev, messageId, action));

    setError(null);

    try {

      const result = await workflowApi.executeAction(workflowId, {

        action_key: action.key,

        params: action.params,

        confirmed: true,

      });

      setMessages((prev) => [

        ...prev,

        result.system_message,

        result.assistant_message,

      ]);

      await onWorkflowUpdated?.();

      await syncMessages();

    } catch (err) {

      setError(err instanceof ApiError ? err.message : "Action failed");

      await syncMessages();

    } finally {

      setRunningAction(null);

    }

  };



  const renderMessageFooter = (chatMessage: ChatMessage) => {

    const workflowMessage = messagesById.get(chatMessage.id);

    if (!workflowMessage || workflowMessage.role !== "assistant") return null;

    const refinementResult = parseWorkflowRefinementResult(workflowMessage.metadata);
    const actions = workflowMessage.actions.filter((action) =>
      shouldRenderMaterialActionInFooter(action, detail),
    );

    if (!refinementResult && !actions.length) return null;

    return (

      <div className="mt-2 space-y-2">

        {refinementResult ? (
          <WorkflowChatOpportunityList
            workflowId={workflowId}
            refinementResult={refinementResult}
          />
        ) : null}

        {actions.map((action) => (

          <WorkflowActionCardButton

            key={`${workflowMessage.id}-${action.key}-${JSON.stringify(action.params ?? {})}`}

            action={action}

            disabled={disabled || Boolean(runningAction)}

            running={

              runningAction?.messageId === workflowMessage.id &&

              runningAction.action.key === action.key

            }

            onConfirm={() => void handleConfirmAction(workflowMessage.id, action)}
            onViewInterviewPlan={onViewInterviewPlan}
            onViewMaterial={onViewMaterial}

          />

        ))}

      </div>

    );

  };



  const typingLabel = runningAction

    ? `Running ${runningAction.action.label}...`

    : undefined;



  return (

    <div className={className}>

      <ChatPanel

        title={title ?? "Refinement co-pilot"}

        subtitle={subtitle ?? "Ask about results or confirm structured follow-up actions"}

        topContent={topContent}

        messages={chatMessages}

        isTyping={sending || loading || Boolean(runningAction)}

        typingLabel={typingLabel}

        renderMessageFooter={renderMessageFooter}

        bottomContent={
          (activeTailorSelection && detail && onWorkflowUpdated) ||
          (activeTailoredMaterialId && !activeTailorSelection) ||
          (activeCoverLetterMaterialId && !activeTailorSelection) ? (
            <div className="space-y-3">
              {activeTailorSelection && detail && onWorkflowUpdated ? (
                <WorkflowTailorSelector
                  workflowId={workflowId}
                  detail={{
                    ...detail,
                    tailor_selection_pending:
                      activeTailorSelection.pending ?? detail.tailor_selection_pending,
                    tailor_options:
                      activeTailorSelection.tailor_options ?? detail.tailor_options,
                  }}
                  onWorkflowUpdated={onWorkflowUpdated}
                />
              ) : null}
              {activeTailoredMaterialId && !activeTailorSelection ? (
                <WorkflowMaterialResult
                  materialId={activeTailoredMaterialId}
                  highlighted={highlightedMaterialId === activeTailoredMaterialId}
                />
              ) : null}
              {activeCoverLetterMaterialId && !activeTailorSelection ? (
                <WorkflowMaterialResult
                  materialId={activeCoverLetterMaterialId}
                  highlighted={highlightedMaterialId === activeCoverLetterMaterialId}
                />
              ) : null}
            </div>
          ) : null
        }

        quickReplies={quickReplies}

        onQuickReply={handleQuickReply}

        inputValue={inputValue}

        onInputChange={setInputValue}

        onSend={() => void handleSend()}

        inputPlaceholder="List applications, request interview prep, tailor a resume..."

        disabled={disabled || sending || loading || Boolean(runningAction)}

        className="h-full min-h-0"

      />



      {error ? <p className="mt-2 text-sm text-destructive">{error}</p> : null}

    </div>

  );

}


