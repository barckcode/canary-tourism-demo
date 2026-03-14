import * as d3 from "d3";
import { formatCompactNumber } from "../../utils/format";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ScenarioPoint {
  period: string;
  value: number;
}

export interface ScenarioResultData {
  baseline_forecast: ScenarioPoint[];
  scenario_forecast: ScenarioPoint[];
  impact_summary: Record<string, number>;
}

export interface ParsedPoint {
  date: Date;
  value: number;
}

export interface CombinedPoint {
  date: Date;
  baseline: number;
  scenario: number;
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

export const MARGIN = { top: 24, right: 30, bottom: 40, left: 65 };

export const COLORS = {
  baseline: "#0ea5e9",
  scenario: "#f59e0b",
  positive: "#22c55e",
  negative: "#ef4444",
};

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

/** @deprecated Use `formatCompactNumber` from `utils/format` directly. */
export const formatValue = formatCompactNumber;

export function parseScenarioData(data: ScenarioResultData): {
  baselineData: ParsedPoint[];
  scenarioData: ParsedPoint[];
  combinedData: CombinedPoint[];
} {
  const baselineData = data.baseline_forecast.map((d) => ({
    date: new Date(d.period + "-01"),
    value: d.value,
  }));
  const scenarioData = data.scenario_forecast.map((d) => ({
    date: new Date(d.period + "-01"),
    value: d.value,
  }));
  const combinedData = baselineData.map((b, i) => ({
    date: b.date,
    baseline: b.value,
    scenario: scenarioData[i]?.value ?? b.value,
  }));
  return { baselineData, scenarioData, combinedData };
}

export function computeDimensions(width: number, height: number): Dimensions {
  return {
    width,
    height,
    innerWidth: width - MARGIN.left - MARGIN.right,
    innerHeight: height - MARGIN.top - MARGIN.bottom,
    margin: MARGIN,
  };
}

export function setupScales(
  baselineData: ParsedPoint[],
  scenarioData: ParsedPoint[],
  dims: Dimensions
): Scales {
  const allDates = baselineData.map((d) => d.date);
  const allValues = [
    ...baselineData.map((d) => d.value),
    ...scenarioData.map((d) => d.value),
  ];

  const x = d3
    .scaleTime()
    .domain(d3.extent(allDates) as [Date, Date])
    .range([0, dims.innerWidth]);

  const y = d3
    .scaleLinear()
    .domain([
      Math.max(0, (d3.min(allValues) || 0) * 0.9),
      (d3.max(allValues) || 0) * 1.08,
    ])
    .range([dims.innerHeight, 0]);

  return { x, y };
}

// ---------------------------------------------------------------------------
// Rendering helpers (mutate the SVG group but are deterministic given inputs)
// ---------------------------------------------------------------------------

export function renderGridLines(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  scales: Scales,
  dims: Dimensions
): void {
  g.append("g")
    .selectAll("line")
    .data(scales.y.ticks(6))
    .join("line")
    .attr("x1", 0)
    .attr("x2", dims.innerWidth)
    .attr("y1", (d) => scales.y(d))
    .attr("y2", (d) => scales.y(d))
    .attr("stroke", "rgba(255,255,255,0.05)")
    .attr("stroke-width", 1);
}

export function renderAxes(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  scales: Scales,
  dims: Dimensions
): void {
  // X axis
  g.append("g")
    .attr("transform", `translate(0,${dims.innerHeight})`)
    .call(
      d3
        .axisBottom(scales.x)
        .ticks(d3.timeMonth.every(1))
        .tickFormat((d) => d3.timeFormat("%b")(d as Date))
    )
    .call((sel) =>
      sel.select(".domain").attr("stroke", "rgba(255,255,255,0.1)")
    )
    .call((sel) =>
      sel.selectAll(".tick line").attr("stroke", "rgba(255,255,255,0.1)")
    )
    .call((sel) =>
      sel
        .selectAll(".tick text")
        .attr("fill", "rgba(255,255,255,0.4)")
        .attr("font-size", "11px")
    );

  // Y axis
  g.append("g")
    .call(
      d3
        .axisLeft(scales.y)
        .ticks(6)
        .tickFormat((d) => formatValue(d as number))
    )
    .call((sel) =>
      sel.select(".domain").attr("stroke", "rgba(255,255,255,0.1)")
    )
    .call((sel) =>
      sel.selectAll(".tick line").attr("stroke", "rgba(255,255,255,0.1)")
    )
    .call((sel) =>
      sel
        .selectAll(".tick text")
        .attr("fill", "rgba(255,255,255,0.4)")
        .attr("font-size", "11px")
    );

  // Y axis label
  g.append("text")
    .attr("transform", "rotate(-90)")
    .attr("x", -dims.innerHeight / 2)
    .attr("y", -50)
    .attr("text-anchor", "middle")
    .attr("fill", "rgba(255,255,255,0.3)")
    .attr("font-size", "11px")
    .text("Arrivals");
}

export function renderAreas(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  combinedData: CombinedPoint[],
  scales: Scales
): void {
  const positiveArea = d3
    .area<CombinedPoint>()
    .x((d) => scales.x(d.date))
    .y0((d) => scales.y(d.baseline))
    .y1((d) => scales.y(Math.max(d.scenario, d.baseline)))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(combinedData)
    .attr("d", positiveArea)
    .attr("fill", `${COLORS.positive}18`)
    .attr("stroke", "none");

  const negativeArea = d3
    .area<CombinedPoint>()
    .x((d) => scales.x(d.date))
    .y0((d) => scales.y(d.baseline))
    .y1((d) => scales.y(Math.min(d.scenario, d.baseline)))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(combinedData)
    .attr("d", negativeArea)
    .attr("fill", `${COLORS.negative}18`)
    .attr("stroke", "none");
}

export function renderLines(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  baselineData: ParsedPoint[],
  scenarioData: ParsedPoint[],
  scales: Scales
): void {
  const lineGen = d3
    .line<ParsedPoint>()
    .x((d) => scales.x(d.date))
    .y((d) => scales.y(d.value))
    .curve(d3.curveMonotoneX);

  // Baseline line
  g.append("path")
    .datum(baselineData)
    .attr("d", lineGen)
    .attr("fill", "none")
    .attr("stroke", COLORS.baseline)
    .attr("stroke-width", 2);

  // Scenario line with animation
  const scenarioPath = g
    .append("path")
    .datum(scenarioData)
    .attr("d", lineGen)
    .attr("fill", "none")
    .attr("stroke", COLORS.scenario)
    .attr("stroke-width", 2.5);

  const totalLength = scenarioPath.node()?.getTotalLength() ?? 0;
  if (totalLength > 0) {
    scenarioPath
      .attr("stroke-dasharray", `${totalLength} ${totalLength}`)
      .attr("stroke-dashoffset", totalLength)
      .transition()
      .duration(1200)
      .ease(d3.easeCubicOut)
      .attr("stroke-dashoffset", 0);
  }
}

export function setupTooltip(
  svg: d3.Selection<SVGSVGElement, unknown, null, undefined>,
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  combinedData: CombinedPoint[],
  scales: Scales,
  dims: Dimensions
): void {
  const { x, y } = scales;
  const { innerWidth: w, innerHeight: h } = dims;

  const focus = g.append("g").style("display", "none");

  focus
    .append("circle")
    .attr("class", "dot-baseline")
    .attr("r", 4)
    .attr("fill", COLORS.baseline)
    .attr("stroke", "#fff")
    .attr("stroke-width", 1.5);

  focus
    .append("circle")
    .attr("class", "dot-scenario")
    .attr("r", 4)
    .attr("fill", COLORS.scenario)
    .attr("stroke", "#fff")
    .attr("stroke-width", 1.5);

  const tooltipG = g
    .append("g")
    .attr("class", "tooltip-g")
    .style("display", "none");

  tooltipG
    .append("rect")
    .attr("rx", 6)
    .attr("fill", "rgba(17,24,39,0.92)")
    .attr("stroke", "rgba(255,255,255,0.1)")
    .attr("stroke-width", 1);

  const tooltipDate = tooltipG
    .append("text")
    .attr("fill", "rgba(255,255,255,0.6)")
    .attr("font-size", "10px");

  const tooltipBaseline = tooltipG
    .append("text")
    .attr("fill", COLORS.baseline)
    .attr("font-size", "11px")
    .attr("font-weight", "600");

  const tooltipScenario = tooltipG
    .append("text")
    .attr("fill", COLORS.scenario)
    .attr("font-size", "11px")
    .attr("font-weight", "600");

  const tooltipDiff = tooltipG
    .append("text")
    .attr("font-size", "10px")
    .attr("font-weight", "500");

  const bisect = d3.bisector<CombinedPoint, Date>((d) => d.date).left;

  const crosshairLine = g
    .append("line")
    .style("display", "none")
    .attr("stroke", "rgba(255,255,255,0.15)")
    .attr("stroke-width", 1)
    .attr("stroke-dasharray", "3,3");

  svg
    .append("rect")
    .attr("width", w)
    .attr("height", h)
    .attr("transform", `translate(${dims.margin.left},${dims.margin.top})`)
    .attr("fill", "transparent")
    .on("mouseover", () => {
      focus.style("display", null);
      tooltipG.style("display", null);
      crosshairLine.style("display", null);
    })
    .on("mouseout", () => {
      focus.style("display", "none");
      tooltipG.style("display", "none");
      crosshairLine.style("display", "none");
    })
    .on("mousemove", (event) => {
      const [mx] = d3.pointer(event);
      const dateAtMouse = x.invert(mx);
      const idx = Math.min(
        bisect(combinedData, dateAtMouse),
        combinedData.length - 1
      );
      const d = combinedData[idx];
      if (!d) return;

      const cx = x(d.date);
      const cyBase = y(d.baseline);
      const cyScen = y(d.scenario);

      focus.select(".dot-baseline").attr("cx", cx).attr("cy", cyBase);
      focus.select(".dot-scenario").attr("cx", cx).attr("cy", cyScen);

      crosshairLine
        .attr("x1", cx)
        .attr("x2", cx)
        .attr("y1", 0)
        .attr("y2", h);

      const formattedDate = d3.timeFormat("%b %Y")(d.date);
      const diffPct =
        d.baseline !== 0
          ? (((d.scenario - d.baseline) / d.baseline) * 100).toFixed(1)
          : "0.0";
      const diffPositive = d.scenario >= d.baseline;

      tooltipDate.text(formattedDate);
      tooltipBaseline.text(`Baseline: ${formatValue(d.baseline)}`);
      tooltipScenario.text(`Scenario: ${formatValue(d.scenario)}`);
      tooltipDiff
        .text(`${diffPositive ? "+" : ""}${diffPct}%`)
        .attr("fill", diffPositive ? COLORS.positive : COLORS.negative);

      const tooltipW = 140;
      const tooltipH = 72;
      const tooltipX =
        cx + 14 > w - tooltipW ? cx - tooltipW - 14 : cx + 14;
      const tooltipY = Math.min(
        Math.max(0, Math.min(cyBase, cyScen) - tooltipH / 2),
        h - tooltipH
      );

      tooltipG.attr("transform", `translate(${tooltipX},${tooltipY})`);
      tooltipG
        .select("rect")
        .attr("width", tooltipW)
        .attr("height", tooltipH);
      tooltipDate.attr("x", 8).attr("y", 16);
      tooltipBaseline.attr("x", 8).attr("y", 32);
      tooltipScenario.attr("x", 8).attr("y", 48);
      tooltipDiff.attr("x", 8).attr("y", 64);
    });
}

export function renderLegend(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  dims: Dimensions
): void {
  const legend = g
    .append("g")
    .attr("transform", `translate(${dims.innerWidth - 240},${-8})`);

  // Baseline legend
  legend
    .append("line")
    .attr("x1", 0)
    .attr("x2", 20)
    .attr("y1", 0)
    .attr("y2", 0)
    .attr("stroke", COLORS.baseline)
    .attr("stroke-width", 2);
  legend
    .append("text")
    .attr("x", 26)
    .attr("y", 4)
    .attr("fill", "rgba(255,255,255,0.5)")
    .attr("font-size", "10px")
    .text("Baseline");

  // Scenario legend
  legend
    .append("line")
    .attr("x1", 90)
    .attr("x2", 110)
    .attr("y1", 0)
    .attr("y2", 0)
    .attr("stroke", COLORS.scenario)
    .attr("stroke-width", 2.5);
  legend
    .append("text")
    .attr("x", 116)
    .attr("y", 4)
    .attr("fill", "rgba(255,255,255,0.5)")
    .attr("font-size", "10px")
    .text("Scenario");

  // Positive area legend
  legend
    .append("rect")
    .attr("x", 185)
    .attr("y", -5)
    .attr("width", 10)
    .attr("height", 10)
    .attr("fill", `${COLORS.positive}30`)
    .attr("stroke", COLORS.positive)
    .attr("stroke-width", 0.5);
  legend
    .append("text")
    .attr("x", 200)
    .attr("y", 4)
    .attr("fill", "rgba(255,255,255,0.5)")
    .attr("font-size", "10px")
    .text("+/-");
}
