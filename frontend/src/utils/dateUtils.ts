/**
 * Parse a "YYYY-MM" period string into a local Date (1st of that month).
 *
 * Using the Date component constructor `new Date(year, month, day)` avoids the
 * UTC-midnight interpretation that `new Date("YYYY-MM-DD")` triggers, which can
 * display the wrong month in negative UTC offsets (e.g., Canary Islands winter).
 */
export function parsePeriodToDate(period: string): Date {
  const [year, month] = period.split("-").map(Number);
  return new Date(year, month - 1, 1);
}
