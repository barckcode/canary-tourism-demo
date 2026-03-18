import { describe, it, expect, vi, beforeAll } from "vitest";
import * as d3 from "d3";
import {
  type ParsedPoint,
  computeDimensions,
  setupScales,
  setupTooltip,
} from "./sparklineChartHelpers";

// Polyfill Touch for jsdom which does not support it
beforeAll(() => {
  if (typeof globalThis.Touch === "undefined") {
    (globalThis as Record<string, unknown>).Touch = class Touch {
      identifier: number;
      target: EventTarget;
      clientX: number;
      clientY: number;
      pageX: number;
      pageY: number;
      screenX: number;
      screenY: number;
      constructor(init: {
        identifier: number;
        target: EventTarget;
        clientX?: number;
        clientY?: number;
      }) {
        this.identifier = init.identifier;
        this.target = init.target;
        this.clientX = init.clientX ?? 0;
        this.clientY = init.clientY ?? 0;
        this.pageX = this.clientX;
        this.pageY = this.clientY;
        this.screenX = this.clientX;
        this.screenY = this.clientY;
      }
    };
  }
});

function createTestSvg(): SVGSVGElement {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("width", "400");
  svg.setAttribute("height", "200");
  document.body.appendChild(svg);
  return svg;
}

function createTestData(): ParsedPoint[] {
  return [
    { date: new Date(2024, 0, 1), value: 100 },
    { date: new Date(2024, 1, 1), value: 200 },
    { date: new Date(2024, 2, 1), value: 150 },
  ];
}

function setupTestTooltip() {
  const svgEl = createTestSvg();
  const svgSel = d3.select(svgEl) as d3.Selection<
    SVGSVGElement,
    unknown,
    null,
    undefined
  >;
  const dims = computeDimensions(400, 200);
  const points = createTestData();

  const g = svgSel
    .append("g")
    .attr(
      "transform",
      `translate(${dims.margin.left},${dims.margin.top})`
    ) as d3.Selection<SVGGElement, unknown, null, undefined>;

  const scales = setupScales(points, dims);
  setupTooltip(svgSel, g, points, scales, dims);

  const overlayRect = svgEl.querySelector(
    "svg > rect"
  ) as SVGRectElement;

  return { svgEl, g, overlayRect };
}

describe("sparklineChartHelpers setupTooltip", () => {
  it("creates an overlay rect for mouse and touch interaction", () => {
    const { svgEl, overlayRect } = setupTestTooltip();

    expect(overlayRect).toBeTruthy();
    expect(overlayRect.getAttribute("fill")).toBe("transparent");

    document.body.removeChild(svgEl);
  });

  it("attaches touch event listeners that call preventDefault", () => {
    const { svgEl, overlayRect } = setupTestTooltip();

    // Create touch events with cancelable: true
    const touchStartEvent = new TouchEvent("touchstart", {
      touches: [
        new Touch({
          identifier: 0,
          target: overlayRect,
          clientX: 100,
          clientY: 100,
        }),
      ],
      cancelable: true,
    });

    const touchMoveEvent = new TouchEvent("touchmove", {
      touches: [
        new Touch({
          identifier: 0,
          target: overlayRect,
          clientX: 150,
          clientY: 100,
        }),
      ],
      cancelable: true,
    });

    // Dispatching should not throw
    overlayRect.dispatchEvent(touchStartEvent);
    overlayRect.dispatchEvent(touchMoveEvent);

    // touchstart and touchmove should have been prevented
    expect(touchStartEvent.defaultPrevented).toBe(true);
    expect(touchMoveEvent.defaultPrevented).toBe(true);

    document.body.removeChild(svgEl);
  });

  it("shows tooltip on touchstart and hides on touchend", () => {
    const { svgEl, g, overlayRect } = setupTestTooltip();

    const focusDot = g.select("circle").node() as SVGCircleElement;
    const tooltipGroup = g
      .select(".sparkline-tooltip")
      .node() as SVGGElement;

    // Initially hidden
    expect(focusDot.style.display).toBe("none");
    expect(tooltipGroup.style.display).toBe("none");

    // Dispatch touchstart
    overlayRect.dispatchEvent(
      new TouchEvent("touchstart", {
        touches: [
          new Touch({
            identifier: 0,
            target: overlayRect,
            clientX: 100,
            clientY: 100,
          }),
        ],
        cancelable: true,
      })
    );

    // After touchstart, tooltip elements should be visible
    expect(focusDot.style.display).not.toBe("none");
    expect(tooltipGroup.style.display).not.toBe("none");

    // Dispatch touchend
    overlayRect.dispatchEvent(
      new TouchEvent("touchend", {
        changedTouches: [
          new Touch({
            identifier: 0,
            target: overlayRect,
            clientX: 100,
            clientY: 100,
          }),
        ],
      })
    );

    // After touchend, tooltip elements should be hidden again
    expect(focusDot.style.display).toBe("none");
    expect(tooltipGroup.style.display).toBe("none");

    document.body.removeChild(svgEl);
  });

  it("does not break existing mouse event behavior", () => {
    const { svgEl, g, overlayRect } = setupTestTooltip();

    const focusDot = g.select("circle").node() as SVGCircleElement;
    const tooltipGroup = g
      .select(".sparkline-tooltip")
      .node() as SVGGElement;

    // mouseover should show
    overlayRect.dispatchEvent(new MouseEvent("mouseover"));
    expect(focusDot.style.display).not.toBe("none");
    expect(tooltipGroup.style.display).not.toBe("none");

    // mouseout should hide
    overlayRect.dispatchEvent(new MouseEvent("mouseout"));
    expect(focusDot.style.display).toBe("none");
    expect(tooltipGroup.style.display).toBe("none");

    document.body.removeChild(svgEl);
  });
});
