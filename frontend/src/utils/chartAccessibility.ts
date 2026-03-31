/**
 * Keyboard accessibility helpers for chart tooltips.
 * Implements WCAG 1.4.13 — Content on Hover or Focus (dismissible).
 */

/**
 * Adds keyboard ESC dismissal for chart tooltips.
 * Call this in the chart's useEffect setup, and invoke the returned
 * cleanup function when the effect tears down.
 */
export function setupTooltipKeyboardDismiss(
  element: SVGSVGElement | HTMLElement | null,
  hideTooltip: () => void
): () => void {
  if (!element) return () => {};

  const handleKeyDown = (e: Event) => {
    if ((e as KeyboardEvent).key === "Escape") {
      hideTooltip();
    }
  };

  element.addEventListener("keydown", handleKeyDown);
  return () => element.removeEventListener("keydown", handleKeyDown);
}
