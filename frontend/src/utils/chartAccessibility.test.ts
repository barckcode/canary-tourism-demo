import { describe, it, expect, vi } from "vitest";
import { setupTooltipKeyboardDismiss } from "./chartAccessibility";

describe("setupTooltipKeyboardDismiss", () => {
  it("calls hideTooltip when Escape is pressed", () => {
    const element = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    const hideTooltip = vi.fn();

    const cleanup = setupTooltipKeyboardDismiss(element, hideTooltip);

    element.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(hideTooltip).toHaveBeenCalledTimes(1);

    cleanup();
  });

  it("does not call hideTooltip for non-Escape keys", () => {
    const element = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    const hideTooltip = vi.fn();

    const cleanup = setupTooltipKeyboardDismiss(element, hideTooltip);

    element.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    element.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab" }));
    element.dispatchEvent(new KeyboardEvent("keydown", { key: "a" }));
    expect(hideTooltip).not.toHaveBeenCalled();

    cleanup();
  });

  it("removes the event listener on cleanup", () => {
    const element = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    const hideTooltip = vi.fn();

    const cleanup = setupTooltipKeyboardDismiss(element, hideTooltip);
    cleanup();

    element.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(hideTooltip).not.toHaveBeenCalled();
  });

  it("returns a no-op cleanup when element is null", () => {
    const hideTooltip = vi.fn();
    const cleanup = setupTooltipKeyboardDismiss(null, hideTooltip);

    expect(typeof cleanup).toBe("function");
    // Should not throw
    cleanup();
  });

  it("works with HTMLElement (for map container)", () => {
    const element = document.createElement("div");
    const hideTooltip = vi.fn();

    const cleanup = setupTooltipKeyboardDismiss(element, hideTooltip);

    element.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(hideTooltip).toHaveBeenCalledTimes(1);

    cleanup();
  });
});
