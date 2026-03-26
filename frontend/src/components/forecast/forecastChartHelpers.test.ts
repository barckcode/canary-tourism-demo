import { describe, it, expect } from "vitest";
import * as d3 from "d3";
import {
  type TimeSeriesPoint,
  type ForecastPoint,
  computeDimensions,
  setupScales,
  renderLines,
  renderDividerLine,
  renderConfidenceBands,
} from "./forecastChartHelpers";

// ---------------------------------------------------------------------------
// Helper to create a detached SVG <g> element for rendering tests
// ---------------------------------------------------------------------------

function createSvgG(): d3.Selection<SVGGElement, unknown, null, undefined> {
  const svg = d3.create("svg");
  return svg.append("g") as d3.Selection<
    SVGGElement,
    unknown,
    null,
    undefined
  >;
}

function makeForecastPoints(count: number): ForecastPoint[] {
  return Array.from({ length: count }, (_, i) => ({
    date: new Date(2026, i + 1, 1),
    value: 500000 + i * 1000,
    ci80Lower: 480000 + i * 1000,
    ci80Upper: 520000 + i * 1000,
    ci95Lower: 470000 + i * 1000,
    ci95Upper: 530000 + i * 1000,
  }));
}

function makeHistoricalPoints(count: number): TimeSeriesPoint[] {
  return Array.from({ length: count }, (_, i) => ({
    date: new Date(2025, i, 1),
    value: 400000 + i * 5000,
  }));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("computeDimensions", () => {
  it("computes inner dimensions correctly", () => {
    const dims = computeDimensions(800, 400);
    expect(dims.innerWidth).toBe(800 - 65 - 30);
    expect(dims.innerHeight).toBe(400 - 20 - 40);
  });
});

describe("renderLines", () => {
  it("does not crash when historical is empty and forecast has data", () => {
    const g = createSvgG();
    const forecast = makeForecastPoints(3);
    const historical: TimeSeriesPoint[] = [];

    // Need valid scales even with empty historical; use forecast dates/values
    const dims = computeDimensions(800, 400);
    const allDates = forecast.map((d) => d.date);
    const allValues = forecast.flatMap((d) => [d.ci95Lower, d.ci95Upper]);

    const x = d3
      .scaleTime()
      .domain(d3.extent(allDates) as [Date, Date])
      .range([0, dims.innerWidth]);
    const y = d3
      .scaleLinear()
      .domain([d3.min(allValues) || 0, d3.max(allValues) || 0])
      .range([dims.innerHeight, 0]);

    // This should not throw
    expect(() => renderLines(g, historical, forecast, { x, y })).not.toThrow();
  });

  it("does not crash when both arrays are empty", () => {
    const g = createSvgG();
    const dims = computeDimensions(800, 400);
    const x = d3.scaleTime().domain([new Date(2025, 0), new Date(2026, 0)]).range([0, dims.innerWidth]);
    const y = d3.scaleLinear().domain([0, 100]).range([dims.innerHeight, 0]);

    expect(() => renderLines(g, [], [], { x, y })).not.toThrow();
  });

  it("renders historical and forecast lines when both have data", () => {
    const g = createSvgG();
    const historical = makeHistoricalPoints(6);
    const forecast = makeForecastPoints(3);
    const dims = computeDimensions(800, 400);
    const scales = setupScales(historical, forecast, dims);

    expect(() => renderLines(g, historical, forecast, scales)).not.toThrow();

    // Should have rendered paths: 1 historical + 1 bridge + 1 forecast = 3
    const paths = g.selectAll("path");
    expect(paths.size()).toBe(3);
  });
});

describe("renderDividerLine", () => {
  it("does not render when historical is empty", () => {
    const g = createSvgG();
    const forecast = makeForecastPoints(3);
    const dims = computeDimensions(800, 400);
    const x = d3.scaleTime().domain([new Date(2026, 1), new Date(2026, 4)]).range([0, dims.innerWidth]);
    const y = d3.scaleLinear().domain([0, 600000]).range([dims.innerHeight, 0]);

    renderDividerLine(g, [], forecast, { x, y }, dims);
    expect(g.selectAll("line").size()).toBe(0);
  });
});

describe("renderConfidenceBands", () => {
  it("does not render when forecast is empty", () => {
    const g = createSvgG();
    const dims = computeDimensions(800, 400);
    const x = d3.scaleTime().domain([new Date(2025, 0), new Date(2026, 0)]).range([0, dims.innerWidth]);
    const y = d3.scaleLinear().domain([0, 600000]).range([dims.innerHeight, 0]);

    renderConfidenceBands(g, [], { x, y });
    expect(g.selectAll("path").size()).toBe(0);
  });
});
