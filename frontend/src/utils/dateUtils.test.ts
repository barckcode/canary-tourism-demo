import { describe, it, expect } from "vitest";
import { parsePeriodToDate } from "./dateUtils";

describe("parsePeriodToDate", () => {
  it("parses a YYYY-MM period into the 1st of that month in local time", () => {
    const date = parsePeriodToDate("2026-01");
    expect(date.getFullYear()).toBe(2026);
    expect(date.getMonth()).toBe(0); // January is 0-indexed
    expect(date.getDate()).toBe(1);
  });

  it("handles December correctly", () => {
    const date = parsePeriodToDate("2025-12");
    expect(date.getFullYear()).toBe(2025);
    expect(date.getMonth()).toBe(11);
    expect(date.getDate()).toBe(1);
  });

  it("returns a local date, not UTC midnight", () => {
    const date = parsePeriodToDate("2026-03");
    // The hours should be 0 in local time, not dependent on UTC offset
    expect(date.getHours()).toBe(0);
    expect(date.getMinutes()).toBe(0);
  });
});
