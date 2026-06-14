import { describe, expect, it } from "vitest";

import { fmtCost, fmtDuration, fmtPct, fmtTokens, shortId } from "./api";

describe("formatters", () => {
  it("fmtPct renders one decimal, em-dash for null", () => {
    expect(fmtPct(89.39)).toBe("89.4%");
    expect(fmtPct(0)).toBe("0.0%");
    expect(fmtPct(null)).toBe("—");
  });

  it("fmtCost uses 4 decimals for sub-cent, dash for zero", () => {
    expect(fmtCost(0.0012)).toBe("$0.0012");
    expect(fmtCost(1.5)).toBe("$1.50");
    expect(fmtCost(0)).toBe("—");
    expect(fmtCost(null)).toBe("—");
  });

  it("fmtTokens sums in+out (locale-agnostic) and dashes zero", () => {
    // Thousands separator is locale-dependent; assert the digits, not the comma.
    expect(fmtTokens(1000, 500).replace(/[.,\s]/g, "")).toBe("1500");
    expect(fmtTokens(0, 0)).toBe("—");
    expect(fmtTokens(null, null)).toBe("—");
  });

  it("fmtDuration scales ms -> s -> m", () => {
    expect(fmtDuration(500)).toBe("500 ms");
    expect(fmtDuration(1500)).toBe("1.5s");
    expect(fmtDuration(65000)).toBe("1m 5s");
    expect(fmtDuration(null)).toBe("—");
  });

  it("shortId truncates", () => {
    expect(shortId("0123456789", 4)).toBe("0123");
    expect(shortId("abc", 8)).toBe("abc");
  });
});
