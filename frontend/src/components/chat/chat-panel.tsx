"use client";

import { useEffect, useRef } from "react";
import { Bot, FileUp, Loader2, Paperclip, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { handleTextareaEnterSubmit } from "@/lib/textarea-keydown";
import { cn } from "@/lib/utils";

export interface ChatMessage {
  id: string;
  role: "assistant" | "user";
  content: string;
  attachmentName?: string;
}

export interface QuickReply {
  label: string;
  value: string;
}

export type FilePickerRef = { open: () => void };

interface ChatPanelProps {
  messages: ChatMessage[];
  isTyping?: boolean;
  quickReplies?: QuickReply[];
  onQuickReply?: (reply: QuickReply) => void;
  inputValue: string;
  onInputChange: (value: string) => void;
  onSend: () => void;
  inputPlaceholder?: string;
  showFileAttach?: boolean;
  onFileAttach?: (file: File) => void;
  filePickerRef?: React.MutableRefObject<FilePickerRef | null>;
  disabled?: boolean;
  quickRepliesDisabled?: boolean;
  fileAttachDisabled?: boolean;
  progress?: { current: number; total: number };
  typingLabel?: string;
  renderMessageFooter?: (message: ChatMessage) => React.ReactNode;
  topContent?: React.ReactNode;
  bottomContent?: React.ReactNode;
  title?: string;
  subtitle?: string;
  className?: string;
}

export function ChatPanel({
  messages,
  isTyping = false,
  quickReplies = [],
  onQuickReply,
  inputValue,
  onInputChange,
  onSend,
  inputPlaceholder = "Type your answer...",
  showFileAttach = false,
  onFileAttach,
  filePickerRef,
  disabled = false,
  quickRepliesDisabled,
  fileAttachDisabled,
  progress,
  typingLabel,
  renderMessageFooter,
  topContent,
  bottomContent,
  title = "CareerPilot",
  subtitle,
  className,
}: ChatPanelProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const attachDisabled = fileAttachDisabled ?? disabled;
  const repliesDisabled = quickRepliesDisabled ?? disabled;

  useEffect(() => {
    if (!filePickerRef) return;
    filePickerRef.current = {
      open: () => fileInputRef.current?.click(),
    };
    return () => {
      filePickerRef.current = null;
    };
  }, [filePickerRef]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    handleTextareaEnterSubmit(e, onSend, {
      disabled,
      hasContent: Boolean(inputValue.trim()),
    });
  };

  return (
    <div
      className={cn(
        "flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-border bg-card/50 backdrop-blur",
        className,
      )}
    >
      <div className="shrink-0 border-b border-border px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Bot className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold">{title}</p>
              {subtitle ? (
                <p className="text-xs text-muted-foreground">{subtitle}</p>
              ) : null}
            </div>
          </div>
          {progress ? (
            <div className="text-right text-xs text-muted-foreground">
              <p>
                Step {progress.current} of {progress.total}
              </p>
              <div className="mt-1 h-1.5 w-24 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary transition-all"
                  style={{
                    width: `${(progress.current / progress.total) * 100}%`,
                  }}
                />
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <ScrollArea className="min-h-0 flex-1 px-5 py-4">
        <div className="space-y-4">
          {topContent ? <div className="space-y-4 pb-2">{topContent}</div> : null}
          {messages.length === 0 && !isTyping && !topContent ? (
            <div className="flex min-h-[200px] items-center justify-center text-sm text-muted-foreground">
              Starting conversation...
            </div>
          ) : null}
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={cn(
                "max-w-[85%]",
                msg.role === "user" ? "ml-auto" : "",
              )}
            >
              <div
                className={cn(
                  "rounded-lg px-4 py-3 text-sm",
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted",
                )}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
                {msg.attachmentName ? (
                  <p className="mt-2 flex items-center gap-1.5 text-xs opacity-80">
                    <FileUp className="h-3.5 w-3.5" />
                    {msg.attachmentName}
                  </p>
                ) : null}
              </div>
              {renderMessageFooter?.(msg)}
            </div>
          ))}
          {isTyping ? (
            <div className="flex max-w-[85%] items-center gap-2 rounded-lg bg-muted px-4 py-3 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              {typingLabel ?? "CareerPilot is thinking..."}
            </div>
          ) : null}
        </div>
      </ScrollArea>

      {bottomContent ? (
        <div className="shrink-0 border-t border-border px-5 py-3">{bottomContent}</div>
      ) : null}

      {quickReplies.length > 0 && !isTyping ? (
        <div className="shrink-0 border-t border-border px-5 py-3">
          <div className="flex flex-wrap gap-2">
            {quickReplies.map((reply) => (
              <button
                key={`${reply.label}-${reply.value}`}
                type="button"
                disabled={repliesDisabled}
                onClick={() => onQuickReply?.(reply)}
                className="rounded-lg border border-border bg-muted/30 px-4 py-2 text-left text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:bg-muted/50 hover:text-foreground disabled:pointer-events-none disabled:opacity-60"
              >
                {reply.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="shrink-0 border-t border-border p-4">
        <div className="flex gap-2">
          {showFileAttach ? (
            <>
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="shrink-0"
                disabled={attachDisabled}
                onClick={() => fileInputRef.current?.click()}
                aria-label="Attach resume"
              >
                <Paperclip className="h-4 w-4" />
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.pdf,.docx"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) onFileAttach?.(file);
                  e.target.value = "";
                }}
              />
            </>
          ) : null}
          <textarea
            value={inputValue}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={inputPlaceholder}
            disabled={disabled}
            className="min-h-[72px] flex-1 resize-none rounded-lg border border-input bg-background px-4 py-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
          />
          <Button
            type="button"
            className="shrink-0 self-end"
            disabled={disabled || !inputValue.trim()}
            onClick={onSend}
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
