/**
 * Compact number formatting utilities.
 *
 * Centralised here so every chart / page uses the same logic.
 */

/**
 * Format a number into a compact string (e.g. 1 200 000 -> "1.2M", 45 000 -> "45K").
 */
export function formatCompactNumber(val: number): string {
  if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`;
  if (val >= 1_000) return `${(val / 1_000).toFixed(0)}K`;
  return `${val}`;
}
