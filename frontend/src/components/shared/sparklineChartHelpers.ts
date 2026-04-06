import * as d3 from "d3";
import { formatCompactNumber } from "../../utils/format";
import { setupTooltipKeyboardDismiss } from "../../utils/chartAccessibility";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SparklineDataPoint {
  period: string;
  value: number;
}

export interface ParsedPoint {
  date: Date;
  value: number;
}

export interface Dimensions {
  width: number;
  height: number;
  innerWidth: number;
  innerHeight: number;
  margin: { top: number; right: number; bottom: number; left: number };
}

export interface Scales {
  x: d3.ScaleTime<number, number>;
  y: d3.ScaleLinear<number, number>;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const MARGIN = { top: 8, right: 12, bottom: 20, left: 6 };

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

export function parsePeriod(p: string): Date {
  const [year, month] = p.split("-").map(Number);
  return new Date(year, month - 1, 1);
}

export function parsePoints(data: SparklineDataPoint[]): ParsedPoint[] {
  return data.map((d) => ({
    date: parsePeriod(d.period),
    value: d.value,
  }));
}

export function computeDimensions(
  width: number,
  height: number
): Dimensions {
  return {
    width,
    height,
    innerWidth: width - MARGIN.left - MARGIN.right,
    innerHeight: height - MARGIN.top - MARGIN.bottom,
    margin: MARGIN,
  };
}

export function setupScales(
  allPoints: ParsedPoint[],
  dims: Dimensions
): Scales {
  const x = d3
    .scaleTime()
    .domain(d3.extent(allPoints, (d) => d.date) as [Date, Date])
    .range([0, dims.innerWidth]);

  const yExtent = d3.extent(allPoints, (d) => d.value) as [number, number];
  let yPadding = (yExtent[1] - yExtent[0]) * 0.15;

  // Guard: when all values are equal the domain collapses to a single point,
  // producing an invalid D3 linear scale. Expand it so the line renders centred.
  if (yExtent[0] === yExtent[1]) {
    const val = yExtent[0];
    yPadding = val !== 0 ? Math.abs(val) * 0.1 : 1;
  }
  const y = d3
    .scaleLinear()
    .domain([Math.max(0, yExtent[0] - yPadding), yExtent[1] + yPadding])
    .range([dims.innerHeight, 0]);

  return { x, y };
}

// ---------------------------------------------------------------------------
// Rendering helpers
// ---------------------------------------------------------------------------

export function renderGridLines(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  scales: Scales,
  dims: Dimensions
): void {
  g.append("g")
    .selectAll("line")
    .data(scales.y.ticks(3))
    .join("line")
    .attr("x1", 0)
    .attr("x2", dims.innerWidth)
    .attr("y1", (d) => scales.y(d))
    .attr("y2", (d) => scales.y(d))
    .attr("stroke", "rgba(255,255,255,0.04)")
    .attr("stroke-width", 1);
}

export function renderXAxis(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  scales: Scales,
  dims: Dimensions
): void {
  g.append("g")
    .attr("transform", `translate(0,${dims.innerHeight})`)
    .call(
      d3
        .axisBottom(scales.x)
        .ticks(d3.timeMonth.every(6))
        .tickFormat((d) => d3.timeFormat("%b '%y")(d as Date))
        .tickSize(0)
    )
    .call((sel) => sel.select(".domain").remove())
    .call((sel) =>
      sel
        .selectAll(".tick text")
        .attr("fill", "rgba(255,255,255,0.3)")
        .attr("font-size", "9px")
        .attr("dy", "10px")
    );
}

export function renderAreaFill(
  svg: d3.Selection<SVGSVGElement, unknown, null, undefined>,
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  historicalPoints: ParsedPoint[],
  scales: Scales,
  dims: Dimensions
): void {
  const defs = svg.append("defs");

  const gradientId = `sparkline-gradient-${Math.random().toString(36).slice(2)}`;
  const gradient = defs
    .append("linearGradient")
    .attr("id", gradientId)
    .attr("x1", "0%")
    .attr("y1", "0%")
    .attr("x2", "0%")
    .attr("y2", "100%");

  gradient
    .append("stop")
    .attr("offset", "0%")
    .attr("stop-color", "#0ea5e9")
    .attr("stop-opacity", 0.25);

  gradient
    .append("stop")
    .attr("offset", "100%")
    .attr("stop-color", "#0ea5e9")
    .attr("stop-opacity", 0);

  const area = d3
    .area<ParsedPoint>()
    .x((d) => scales.x(d.date))
    .y0(dims.innerHeight)
    .y1((d) => scales.y(d.value))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(historicalPoints)
    .attr("d", area)
    .attr("fill", `url(#${gradientId})`);
}

export function renderLines(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  historicalPoints: ParsedPoint[],
  forecastPoints: ParsedPoint[],
  scales: Scales
): void {
  const line = d3
    .line<ParsedPoint>()
    .x((d) => scales.x(d.date))
    .y((d) => scales.y(d.value))
    .curve(d3.curveMonotoneX);

  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Historical line with animation
  const historicalPath = g
    .append("path")
    .datum(historicalPoints)
    .attr("d", line)
    .attr("fill", "none")
    .attr("stroke", "#0ea5e9")
    .attr("stroke-width", 2)
    .attr("stroke-linecap", "round");

  const totalLength = historicalPath.node()?.getTotalLength() || 0;
  if (prefersReducedMotion) {
    historicalPath.attr("stroke-dashoffset", 0);
  } else {
    historicalPath
      .attr("stroke-dasharray", `${totalLength} ${totalLength}`)
      .attr("stroke-dashoffset", totalLength)
      .transition()
      .duration(1200)
      .ease(d3.easeCubicOut)
      .attr("stroke-dashoffset", 0);
  }

  // Forecast dashed extension
  if (forecastPoints.length > 0) {
    const bridgeAndForecast = [
      historicalPoints[historicalPoints.length - 1],
      ...forecastPoints,
    ];

    const forecastPath = g
      .append("path")
      .datum(bridgeAndForecast)
      .attr("d", line)
      .attr("fill", "none")
      .attr("stroke", "#0ea5e9")
      .attr("stroke-width", 1.5)
      .attr("stroke-dasharray", "4,3")
      .attr("stroke-linecap", "round")
      .attr("opacity", 0.5);

    if (!prefersReducedMotion) {
      const forecastLength = forecastPath.node()?.getTotalLength() || 0;
      forecastPath
        .attr(
          "stroke-dasharray",
          `0 ${forecastLength} 0 ${forecastLength}`
        )
        .transition()
        .delay(1200)
        .duration(600)
        .ease(d3.easeCubicOut)
        .attr("stroke-dasharray", "4 3");
    }
  }
}

export function setupTooltip(
  svg: d3.Selection<SVGSVGElement, unknown, null, undefined>,
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  allPoints: ParsedPoint[],
  scales: Scales,
  dims: Dimensions
): () => void {
  const { x, y } = scales;
  const { innerWidth: w, innerHeight: h } = dims;

  const focusDot = g
    .append("circle")
    .attr("r", 3.5)
    .attr("fill", "#0ea5e9")
    .attr("stroke", "#fff")
    .attr("stroke-width", 1.5)
    .style("display", "none");

  const tooltipGroup = g
    .append("g")
    .attr("class", "sparkline-tooltip")
    .style("display", "none")
    .style("pointer-events", "none");

  tooltipGroup
    .append("rect")
    .attr("rx", 4)
    .attr("fill", "rgba(15,23,42,0.92)")
    .attr("stroke", "rgba(255,255,255,0.1)")
    .attr("stroke-width", 0.5);

  const tooltipPeriod = tooltipGroup
    .append("text")
    .attr("fill", "rgba(255,255,255,0.5)")
    .attr("font-size", "9px");

  const tooltipValue = tooltipGroup
    .append("text")
    .attr("fill", "#fff")
    .attr("font-size", "11px")
    .attr("font-weight", "600");

  const bisect = d3.bisector<ParsedPoint, Date>((d) => d.date).left;

  // Shared logic for updating tooltip position and content
  function updateTooltipAt(mx: number): void {
    const dateAtMouse = x.invert(mx);
    let idx = bisect(allPoints, dateAtMouse);
    if (idx >= allPoints.length) idx = allPoints.length - 1;
    if (idx > 0) {
      const d0 = allPoints[idx - 1];
      const d1 = allPoints[idx];
      if (
        dateAtMouse.getTime() - d0.date.getTime() <
        d1.date.getTime() - dateAtMouse.getTime()
      ) {
        idx = idx - 1;
      }
    }
    const d = allPoints[idx];
    if (!d) return;

    const cx = x(d.date);
    const cy = y(d.value);

    focusDot.attr("cx", cx).attr("cy", cy);

    const formattedDate = d3.timeFormat("%b %Y")(d.date);
    const formattedValue = formatCompactNumber(d.value);

    tooltipPeriod.text(formattedDate);
    tooltipValue.text(formattedValue);

    const tooltipW = 72;
    const tooltipH = 36;
    const tooltipX =
      cx + 14 + tooltipW > w ? cx - tooltipW - 10 : cx + 14;
    const tooltipY = Math.max(
      0,
      Math.min(cy - tooltipH / 2, h - tooltipH)
    );

    tooltipGroup.attr(
      "transform",
      `translate(${tooltipX},${tooltipY})`
    );
    tooltipGroup
      .select("rect")
      .attr("width", tooltipW)
      .attr("height", tooltipH);
    tooltipPeriod.attr("x", 8).attr("y", 14);
    tooltipValue.attr("x", 8).attr("y", 28);
  }

  function showTooltip(): void {
    focusDot.style("display", null);
    tooltipGroup.style("display", null);
  }

  function hideTooltip(): void {
    focusDot.style("display", "none");
    tooltipGroup.style("display", "none");
  }

  const overlayRect = svg
    .append("rect")
    .attr("width", w)
    .attr("height", h)
    .attr("transform", `translate(${dims.margin.left},${dims.margin.top})`)
    .attr("fill", "transparent")
    .style("cursor", "crosshair")
    .on("mouseover", showTooltip)
    .on("mouseout", hideTooltip)
    .on("mousemove", (event) => {
      const [mx] = d3.pointer(event);
      updateTooltipAt(mx);
    });

  // Touch support for tablets and mobile devices
  const overlayNode = overlayRect.node();
  if (overlayNode) {
    overlayNode.addEventListener(
      "touchstart",
      (event: TouchEvent) => {
        event.preventDefault();
        showTooltip();
        const touch = event.touches[0];
        const [mx] = d3.pointer(touch, overlayNode);
        updateTooltipAt(mx);
      },
      { passive: false }
    );
    overlayNode.addEventListener(
      "touchmove",
      (event: TouchEvent) => {
        event.preventDefault();
        const touch = event.touches[0];
        const [mx] = d3.pointer(touch, overlayNode);
        updateTooltipAt(mx);
      },
      { passive: false }
    );
    overlayNode.addEventListener("touchend", () => {
      hideTooltip();
    });
  }

  // ESC key dismiss for keyboard accessibility (WCAG 1.4.13)
  const cleanupEsc = setupTooltipKeyboardDismiss(svg.node(), hideTooltip);
  return cleanupEsc;
}
