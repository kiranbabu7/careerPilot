import type { KeyboardEvent } from "react";

/** Enter submits; Shift+Enter inserts a newline (standard chat UX). */
export function handleTextareaEnterSubmit(
  event: KeyboardEvent<HTMLTextAreaElement>,
  onSubmit: () => void,
  options?: { disabled?: boolean; hasContent?: boolean },
): void {
  if (event.key !== "Enter" || event.shiftKey) return;

  event.preventDefault();

  if (event.nativeEvent.isComposing) return;
  if (options?.disabled) return;
  if (options?.hasContent === false) return;

  onSubmit();
}
