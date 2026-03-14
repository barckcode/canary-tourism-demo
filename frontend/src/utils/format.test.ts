import { describe, it, expect } from "vitest";
import { formatCompactNumber } from "./format";

describe("formatCompactNumber", () => {
  it("formats millions with one decimal", () => {
    expect(formatCompactNumber(1_200_000)).toBe("1.2M");
    expect(formatCompactNumber(5_000_000)).toBe("5.0M");
  });

  it("formats thousands without decimals", () => {
    expect(formatCompactNumber(45_000)).toBe("45K");
    expect(formatCompactNumber(1_000)).toBe("1K");
    expect(formatCompactNumber(999_999)).toBe("1000K");
  });

  it("returns raw number for values below 1000", () => {
    expect(formatCompactNumber(500)).toBe("500");
    expect(formatCompactNumber(0)).toBe("0");
    expect(formatCompactNumber(99)).toBe("99");
  });
});
