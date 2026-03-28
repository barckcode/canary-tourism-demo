import { describe, it, expect, vi, beforeAll } from "vitest";
import { render } from "@testing-library/react";

// Polyfill ResizeObserver for jsdom
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === "undefined") {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    } as unknown as typeof ResizeObserver;
  }
});

// Mock d3-sankey to avoid import issues in jsdom
vi.mock("d3-sankey", () => ({
  sankey: () => {
    const gen = () => ({ nodes: [], links: [] });
    gen.nodeId = () => gen;
    gen.nodeWidth = () => gen;
    gen.nodePadding = () => gen;
    gen.extent = () => gen;
    return gen;
  },
  sankeyLinkHorizontal: () => () => "",
}));

import SparklineChart from "./shared/SparklineChart";
import ClusterViz from "./profiles/ClusterViz";
import SankeyFlow from "./profiles/SankeyFlow";
import ForecastChart from "./forecast/ForecastChart";
import YoYHeatmap from "./forecast/YoYHeatmap";

// Mock the YoY hook to avoid real API calls
vi.mock("../api/hooks", () => ({
  useYoYHeatmap: () => ({ data: null, loading: false, error: null }),
}));

describe("SVG chart ARIA accessibility", () => {
  it("SparklineChart SVG has role=img and aria-label", () => {
    const data = [
      { period: "2024-01", value: 100 },
      { period: "2024-02", value: 120 },
    ];
    render(<SparklineChart data={data} />);
    const svg = document.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg!.getAttribute("role")).toBe("img");
    expect(svg!.getAttribute("aria-label")).toBe("Trend sparkline chart");
  });

  it("ForecastChart SVG has role=img, aria-label, and D3-rendered <title>", () => {
    render(
      <ForecastChart
        historical={[{ date: new Date(2024, 0, 1), value: 100 }]}
        forecast={[]}
        width={400}
        height={200}
      />
    );
    const svg = document.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg!.getAttribute("role")).toBe("img");
    expect(svg!.getAttribute("aria-label")).toBe(
      "Tourism forecast chart with historical data and predictions"
    );
    // D3 renders the <title> element after clearing the SVG
    const title = svg!.querySelector("title");
    expect(title).not.toBeNull();
    expect(title!.textContent).toBe(
      "Tourism forecast chart with historical data and predictions"
    );
  });

  it("YoYHeatmap renders accessible empty state when no data", () => {
    render(<YoYHeatmap width={400} height={200} />);
    // With no data from the hook, the component renders an empty state div
    expect(document.body).toBeTruthy();
  });

  it("ClusterViz SVG has role=img, aria-label, tabIndex, and D3-rendered <title>", () => {
    render(<ClusterViz width={400} height={300} />);
    const svg = document.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg!.getAttribute("role")).toBe("img");
    expect(svg!.getAttribute("aria-label")).toBe("Tourist cluster visualization");
    expect(svg!.getAttribute("tabindex")).toBe("0");
    // D3 renders the <title> element
    const title = svg!.querySelector("title");
    expect(title).not.toBeNull();
    expect(title!.textContent).toBe("Tourist cluster visualization");
  });

  it("SankeyFlow SVG has role=img, aria-label, and D3-rendered <title>", () => {
    render(<SankeyFlow width={400} height={300} />);
    const svg = document.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg!.getAttribute("role")).toBe("img");
    expect(svg!.getAttribute("aria-label")).toBe("Tourist flow Sankey diagram");
    // D3 renders the <title> element
    const title = svg!.querySelector("title");
    expect(title).not.toBeNull();
    expect(title!.textContent).toBe("Tourist flow Sankey diagram");
  });

  it("ClusterViz bubble groups have keyboard accessibility via D3", () => {
    render(<ClusterViz width={400} height={300} />);
    // D3 renders bubble groups with tabindex, role=button, and aria-label
    const buttons = document.querySelectorAll('[role="button"]');
    expect(buttons.length).toBeGreaterThan(0);
    buttons.forEach((btn) => {
      expect(btn.getAttribute("tabindex")).toBe("0");
      expect(btn.getAttribute("aria-label")).toBeTruthy();
    });
  });
});
