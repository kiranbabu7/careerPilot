"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ChatPanel, type ChatMessage, type FilePickerRef, type QuickReply } from "@/components/chat/chat-panel";
import { useAuth } from "@/contexts/auth-context";
import {
  ApiError,
  dashboardApi,
  preferencesApi,
  resumeApi,
  type DashboardSummary,
} from "@/lib/api";
import {
  getInitialOnboardingStep,
  getOnboardingSteps,
  parseLocationInput,
  parseSalaryInput,
  parseTags,
  postResumeSummary,
  REMOTE_QUICK_REPLIES,
  skippedResumePromptSteps,
  stepPrompt,
  UPLOAD_RESUME_QUICK_REPLY,
  type OnboardingStep,
} from "@/lib/onboarding";

const TYPING_DELAY_MS = 700;
const COMPLETE_REDIRECT_DELAY_MS = 1500;

function createId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function getNextStep(
  summary: DashboardSummary,
  after: OnboardingStep,
): OnboardingStep {
  const steps = getOnboardingSteps(summary);
  const index = steps.indexOf(after);
  return steps[index + 1] ?? "complete";
}

interface OnboardingChatProps {
  dashboard: DashboardSummary;
  onComplete: (dashboard: DashboardSummary) => void;
}

export function OnboardingChat({ dashboard, onComplete }: OnboardingChatProps) {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeStep, setActiveStep] = useState<OnboardingStep>(() =>
    getInitialOnboardingStep(dashboard),
  );
  const [currentDashboard, setCurrentDashboard] = useState(dashboard);
  const promptedStepsRef = useRef<Set<OnboardingStep>>(
    new Set(skippedResumePromptSteps(dashboard)),
  );
  const completedRef = useRef(false);
  const filePickerRef = useRef<FilePickerRef | null>(null);

  const steps = useMemo(
    () => getOnboardingSteps(currentDashboard),
    [currentDashboard],
  );
  const stepIndex = steps.indexOf(activeStep);
  const progressCurrent = stepIndex >= 0 ? stepIndex + 1 : steps.length;
  const progressTotal = steps.length;

  const appendMessage = useCallback((message: Omit<ChatMessage, "id">) => {
    setMessages((prev) => [...prev, { ...message, id: createId() }]);
  }, []);

  const showBotMessage = useCallback(
    async (step: OnboardingStep) => {
      if (promptedStepsRef.current.has(step)) return;
      promptedStepsRef.current.add(step);
      setIsTyping(true);
      await new Promise((resolve) => setTimeout(resolve, TYPING_DELAY_MS));
      setIsTyping(false);
      appendMessage({ role: "assistant", content: stepPrompt(step, user?.full_name) });
    },
    [appendMessage, user?.full_name],
  );

  useEffect(() => {
    void showBotMessage(activeStep);
  }, [activeStep, showBotMessage]);

  const refreshDashboard = useCallback(async () => {
    const summary = await dashboardApi.summary();
    setCurrentDashboard(summary);
    return summary;
  }, []);

  const finishIfDone = useCallback(
    async (summary: DashboardSummary, nextStep: OnboardingStep) => {
      if (nextStep !== "complete" || completedRef.current) return;
      completedRef.current = true;
      await new Promise((resolve) => setTimeout(resolve, COMPLETE_REDIRECT_DELAY_MS));
      onComplete(summary);
    },
    [onComplete],
  );

  const advanceAfter = useCallback(
    async (completedStep: OnboardingStep) => {
      const summary = await refreshDashboard();
      const nextStep = getNextStep(summary, completedStep);
      setActiveStep(nextStep);
      if (nextStep === "complete") {
        await finishIfDone(summary, nextStep);
      }
      return summary;
    },
    [finishIfDone, refreshDashboard],
  );

  const handleError = (err: unknown) => {
    const message =
      err instanceof ApiError ? err.message : "Something went wrong. Try again.";
    setError(message);
    appendMessage({
      role: "assistant",
      content: `I hit a snag saving that: ${message}. Want to try again?`,
    });
  };

  const saveCareerGoals = async (text: string) => {
    await preferencesApi.update({ career_goals: text.trim() });
    await advanceAfter("career_goals");
  };

  const saveTargetRoles = async (text: string) => {
    const roles = parseTags(text);
    if (roles.length === 0) {
      appendMessage({
        role: "assistant",
        content: "I need at least one target role. Try something like Senior Backend Engineer.",
      });
      return;
    }
    await preferencesApi.update({ target_roles: roles });
    await advanceAfter("target_roles");
  };

  const saveRemotePreference = async (text: string) => {
    const parsed = parseLocationInput(text);

    if (!parsed.remote_preference && parsed.target_locations.length === 0) {
      appendMessage({
        role: "assistant",
        content: "Pick a work style below, or type cities you'd consider (e.g. Remote, Austin).",
      });
      return;
    }

    const update: {
      remote_preference?: string;
      target_locations?: string[];
    } = {};

    if (parsed.remote_preference) {
      update.remote_preference = parsed.remote_preference;
    } else if (parsed.target_locations.length > 0) {
      update.remote_preference = "flexible";
    }
    if (parsed.target_locations.length > 0) {
      update.target_locations = parsed.target_locations;
    }

    await preferencesApi.update(update);
    await advanceAfter("remote_preference");
  };

  const saveSkills = async (text: string) => {
    const trimmed = text.trim();
    if (/^skip$/i.test(trimmed)) {
      await advanceAfter("skills");
      return;
    }
    const skills = parseTags(trimmed);
    if (skills.length === 0) {
      appendMessage({
        role: "assistant",
        content: "List a few skills comma-separated, or type skip.",
      });
      return;
    }
    await preferencesApi.update({ skills });
    await advanceAfter("skills");
  };

  const saveSalary = async (text: string) => {
    const trimmed = text.trim();
    if (/^skip(\s+for\s+now)?$/i.test(trimmed)) {
      await advanceAfter("salary");
      return;
    }
    const parsed = parseSalaryInput(trimmed);
    if (!parsed) {
      appendMessage({
        role: "assistant",
        content:
          "Share a range like 26L-30L, 120k-180k, or 120000-180000, or tap Skip for now.",
      });
      return;
    }
    await preferencesApi.update({
      salary_min: parsed.salary_min,
      salary_max: parsed.salary_max,
    });
    await advanceAfter("salary");
  };

  const handleWelcome = async (text: string) => {
    const affirmative = /^(yes|yeah|yep|sure|ok|okay|let's go|ready|start)/i.test(
      text.trim(),
    );
    if (!affirmative && text.trim().length < 4) {
      appendMessage({
        role: "assistant",
        content: "Whenever you're ready, just say yes or tell me what you're hoping to achieve.",
      });
      return;
    }
    const summary = await refreshDashboard();
    const nextStep = getNextStep(summary, "welcome");
    setActiveStep(nextStep);
    if (nextStep === "complete") {
      await finishIfDone(summary, nextStep);
    }
  };

  const processUserInput = async (text: string, attachmentName?: string) => {
    setError(null);
    setIsSaving(true);
    appendMessage({
      role: "user",
      content: text,
      attachmentName,
    });
    setInput("");

    try {
      switch (activeStep) {
        case "welcome":
          await handleWelcome(text);
          break;
        case "career_goals":
          await saveCareerGoals(text);
          break;
        case "target_roles":
          await saveTargetRoles(text);
          break;
        case "remote_preference":
          await saveRemotePreference(text);
          break;
        case "skills":
          await saveSkills(text);
          break;
        case "salary":
          await saveSalary(text);
          break;
        default:
          break;
      }
    } catch (err) {
      handleError(err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || isSaving || isTyping) return;
    if (activeStep === "resume" || activeStep === "complete") return;
    void processUserInput(trimmed);
  };

  const handleQuickReply = (reply: QuickReply) => {
    if (isSaving || isTyping) return;
    if (reply.value === UPLOAD_RESUME_QUICK_REPLY) {
      filePickerRef.current?.open();
      return;
    }
    void processUserInput(reply.value);
  };

  const handleResumeUpload = async (file: File) => {
    const canUpload =
      activeStep === "resume" || activeStep === "welcome";
    if (!canUpload || isSaving) return;
    setError(null);
    setIsSaving(true);
    appendMessage({
      role: "user",
      content: "Here's my resume.",
      attachmentName: file.name,
    });

    try {
      setIsTyping(true);
      await resumeApi.upload(file);
      setIsTyping(false);
      appendMessage({
        role: "assistant",
        content:
          "Got it — I'm reading your resume and updating your profile. One moment...",
      });
      setIsTyping(true);
      await new Promise((resolve) => setTimeout(resolve, TYPING_DELAY_MS));
      setIsTyping(false);
      const summary = await refreshDashboard();
      appendMessage({
        role: "assistant",
        content: postResumeSummary(summary),
      });
      promptedStepsRef.current.add("welcome");
      promptedStepsRef.current.add("resume");
      const nextStep = getNextStep(summary, "resume");
      setActiveStep(nextStep);
      if (nextStep === "complete") {
        await finishIfDone(summary, nextStep);
      }
    } catch (err) {
      setIsTyping(false);
      handleError(err);
    } finally {
      setIsSaving(false);
    }
  };

  const quickReplies = useMemo((): QuickReply[] => {
    if (isTyping || isSaving) return [];
    switch (activeStep) {
      case "welcome":
        return [
          { label: "Yes, let's go", value: "Yes, let's go" },
          { label: UPLOAD_RESUME_QUICK_REPLY, value: UPLOAD_RESUME_QUICK_REPLY },
        ];
      case "resume":
        return [{ label: UPLOAD_RESUME_QUICK_REPLY, value: UPLOAD_RESUME_QUICK_REPLY }];
      case "remote_preference":
        return REMOTE_QUICK_REPLIES.map((opt) => ({ label: opt.label, value: opt.label }));
      case "skills":
        return [{ label: "Skip for now", value: "Skip for now" }];
      case "salary":
        return [{ label: "Skip for now", value: "Skip for now" }];
      default:
        return [];
    }
  }, [activeStep, isSaving, isTyping]);

  const showResumeAttach = activeStep === "resume" || activeStep === "welcome";
  const inputDisabled =
    isSaving || isTyping || activeStep === "complete" || showResumeAttach;
  const quickRepliesDisabled = isSaving || isTyping || activeStep === "complete";
  const fileAttachDisabled =
    isSaving || isTyping || activeStep === "complete";

  return (
    <div className="flex h-full min-h-0 flex-col p-4 md:p-6">
      <ChatPanel
        className="min-h-0 flex-1"
        messages={messages}
        isTyping={isTyping}
        quickReplies={quickReplies}
        onQuickReply={handleQuickReply}
        inputValue={input}
        onInputChange={setInput}
        onSend={handleSend}
        onFileAttach={(file) => void handleResumeUpload(file)}
        filePickerRef={filePickerRef}
        showFileAttach={showResumeAttach}
        disabled={inputDisabled}
        quickRepliesDisabled={quickRepliesDisabled}
        fileAttachDisabled={fileAttachDisabled}
        inputPlaceholder={
          showResumeAttach
            ? "Attach your resume with the clip icon..."
            : "Type your answer..."
        }
        progress={{ current: progressCurrent, total: progressTotal }}
        title="Profile setup"
        subtitle="Chat with your CareerPilot teammate"
      />
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </div>
  );
}
