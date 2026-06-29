import { describe, expect, it, vi } from "vitest";

import { handleTextareaEnterSubmit } from "@/lib/textarea-keydown";

function createKeyEvent(
  key: string,
  options?: { shiftKey?: boolean; isComposing?: boolean },
): React.KeyboardEvent<HTMLTextAreaElement> {
  return {
    key,
    shiftKey: options?.shiftKey ?? false,
    preventDefault: vi.fn(),
    nativeEvent: { isComposing: options?.isComposing ?? false },
  } as unknown as React.KeyboardEvent<HTMLTextAreaElement>;
}

describe("handleTextareaEnterSubmit", () => {
  it("submits on Enter without Shift", () => {
    const onSubmit = vi.fn();
    const event = createKeyEvent("Enter");

    handleTextareaEnterSubmit(event, onSubmit);

    expect(event.preventDefault).toHaveBeenCalled();
    expect(onSubmit).toHaveBeenCalled();
  });

  it("does not submit on Shift+Enter", () => {
    const onSubmit = vi.fn();
    const event = createKeyEvent("Enter", { shiftKey: true });

    handleTextareaEnterSubmit(event, onSubmit);

    expect(event.preventDefault).not.toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("does not submit when disabled or empty", () => {
    const onSubmit = vi.fn();

    handleTextareaEnterSubmit(createKeyEvent("Enter"), onSubmit, { disabled: true });
    handleTextareaEnterSubmit(createKeyEvent("Enter"), onSubmit, { hasContent: false });

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("does not submit during IME composition", () => {
    const onSubmit = vi.fn();
    const event = createKeyEvent("Enter", { isComposing: true });

    handleTextareaEnterSubmit(event, onSubmit);

    expect(event.preventDefault).toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
