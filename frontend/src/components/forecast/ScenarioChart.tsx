import { useEffect, useRef, useMemo } from "react";
import * as d3 from "d3";

export interface ScenarioPoint {
  period: string;
  value: number;
}

export interface ScenarioResultData {
  baseline_forecast: ScenarioPoint[];
  scenario_forecast: ScenarioPoint[];
  impact_summary: Record<string, number>;
}

interface ScenarioChartProps {
  data: ScenarioResultData;
  width: number;
  height: number;
}

const MARGIN = { top: 24, right: 30, bottom: 40, left: 65 };

const COLORS = {
  baseline: "#0ea5e9",
  scenario: "#f59e0b",
  positive: "#22c55e",
  negative: "#ef4444",
};

function formatValue(val: number): string {
  if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`;
  if (val >= 1_000) return `${(val / 1_000).toFixed(0)}K`;
  return `${val}`;
}

/** Compute impact statistics from baseline vs scenario data */
function computeImpactStats(
  baseline: ScenarioPoint[],
  scenario: ScenarioPoint[]
) {
  if (baseline.length === 0 || scenario.length === 0) {
    return { avgChangePct: 0, direction: "neutral" as const, maxImpactMonth: "" };
  }

  const changes = baseline.map((b, i) => {
    const s = scenario[i];
    if (!s || b.value === 0) return 0;
    return ((s.value - b.value) / b.value) * 100;
  });

  const avgChangePct = changes.reduce((a, b) => a + b, 0) / changes.length;

  const absChanges = changes.map(Math.abs);
  const maxIdx = absChanges.indexOf(Math.max(...absChanges));
  const maxImpactMonth = baseline[maxIdx]?.period ?? "";

  const direction =
    avgChangePct > 0.05
      ? ("increase" as const)
      : avgChangePct < -0.05
        ? ("decrease" as const)
        : ("neutral" as const);

  return { avgChangePct, direction, maxImpactMonth };
}

export function ScenarioImpactStats({
  data,
}: {
  data: ScenarioResultData;
}) {
  const stats = useMemo(
    () =>
      computeImpactStats(data.baseline_forecast, data.scenario_forecast),
    [data]
  );

  const isPositive = stats.direction === "increase";
  const isNeutral = stats.direction === "neutral";

  return (
    <div className="grid grid-cols-3 gap-4 mt-4">
      <div className="bg-white/5 backdrop-blur rounded-lg p-4 text-center">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
          Avg Change
        </p>
        <p
          className={`text-xl font-bold font-mono ${
            isNeutral
              ? "text-gray-400"
              : isPositive
                ? "text-tropical-400"
                : "text-red-400"
          }`}
        >
          {stats.avgChangePct > 0 ? "+" : ""}
          {stats.avgChangePct.toFixed(1)}%
        </p>
      </div>
      <div className="bg-white/5 backdrop-blur rounded-lg p-4 text-center">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
          Direction
        </p>
        <p
          className={`text-xl font-bold capitalize ${
            isNeutral
              ? "text-gray-400"
              : isPositive
                ? "text-tropical-400"
                : "text-red-400"
          }`}
        >
          {stats.direction === "increase"
            ? "Increase"
            : stats.direction === "decrease"
              ? "Decrease"
              : "Neutral"}
        </p>
      </div>
      <div className="bg-white/5 backdrop-blur rounded-lg p-4 text-center">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
          Max Impact
        </p>
        <p className="text-xl font-bold text-volcanic-400 font-mono">
          {stats.maxImpactMonth || "N/A"}
        </p>
      </div>
    </div>
  );
}

export default function ScenarioChart({
  data,
  width,
  height,
}: ScenarioChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || width <= 0 || height <= 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const w = width - MARGIN.left - MARGIN.right;
    const h = height - MARGIN.top - MARGIN.bottom;

    const g = svg
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${MARGIN.left},${MARGIN.top})`);

    // Parse dates
    const baselineData = data.baseline_forecast.map((d) => ({
      date: new Date(d.period + "-01"),
      value: d.value,
    }));
    const scenarioData = data.scenario_forecast.map((d) => ({
      date: new Date(d.period + "-01"),
      value: d.value,
    }));

    if (baselineData.length === 0) return;

    // Scales
    const allDates = baselineData.map((d) => d.date);
    const allValues = [
      ...baselineData.map((d) => d.value),
      ...scenarioData.map((d) => d.value),
    ];

    const x = d3
      .scaleTime()
      .domain(d3.extent(allDates) as [Date, Date])
      .range([0, w]);

    const y = d3
      .scaleLinear()
      .domain([
        Math.max(0, (d3.min(allValues) || 0) * 0.9),
        (d3.max(allValues) || 0) * 1.08,
      ])
      .range([h, 0]);

    // Grid lines
    g.append("g")
      .selectAll("line")
      .data(y.ticks(6))
      .join("line")
      .attr("x1", 0)
      .attr("x2", w)
      .attr("y1", (d) => y(d))
      .attr("y2", (d) => y(d))
      .attr("stroke", "rgba(255,255,255,0.05)")
      .attr("stroke-width", 1);

    // X axis
    g.append("g")
      .attr("transform", `translate(0,${h})`)
      .call(
        d3
          .axisBottom(x)
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
          .axisLeft(y)
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
      .attr("x", -h / 2)
      .attr("y", -50)
      .attr("text-anchor", "middle")
      .attr("fill", "rgba(255,255,255,0.3)")
      .attr("font-size", "11px")
      .text("Arrivals");

    // Area fill between baseline and scenario lines
    // We need to split into segments where scenario > baseline (green) and scenario < baseline (red)
    const combinedData = baselineData.map((b, i) => ({
      date: b.date,
      baseline: b.value,
      scenario: scenarioData[i]?.value ?? b.value,
    }));

    // Positive area (scenario > baseline)
    const positiveArea = d3
      .area<{ date: Date; baseline: number; scenario: number }>()
      .x((d) => x(d.date))
      .y0((d) => y(d.baseline))
      .y1((d) => y(Math.max(d.scenario, d.baseline)))
      .curve(d3.curveMonotoneX);

    g.append("path")
      .datum(combinedData)
      .attr("d", positiveArea)
      .attr("fill", `${COLORS.positive}18`)
      .attr("stroke", "none");

    // Negative area (scenario < baseline)
    const negativeArea = d3
      .area<{ date: Date; baseline: number; scenario: number }>()
      .x((d) => x(d.date))
      .y0((d) => y(d.baseline))
      .y1((d) => y(Math.min(d.scenario, d.baseline)))
      .curve(d3.curveMonotoneX);

    g.append("path")
      .datum(combinedData)
      .attr("d", negativeArea)
      .attr("fill", `${COLORS.negative}18`)
      .attr("stroke", "none");

    // Baseline line
    const lineGen = d3
      .line<{ date: Date; value: number }>()
      .x((d) => x(d.date))
      .y((d) => y(d.value))
      .curve(d3.curveMonotoneX);

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

    // Animate: draw the scenario line
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

    // Tooltip
    const focus = g.append("g").style("display", "none");

    // Baseline dot
    focus
      .append("circle")
      .attr("class", "dot-baseline")
      .attr("r", 4)
      .attr("fill", COLORS.baseline)
      .attr("stroke", "#fff")
      .attr("stroke-width", 1.5);

    // Scenario dot
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

    const bisect = d3.bisector<{ date: Date; baseline: number; scenario: number }, Date>(
      (d) => d.date
    ).left;

    // Crosshair line
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
      .attr("transform", `translate(${MARGIN.left},${MARGIN.top})`)
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

    // Legend
    const legend = g
      .append("g")
      .attr("transform", `translate(${w - 240},${-8})`);

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
  }, [data, width, height]);

  return <svg ref={svgRef} className="overflow-visible" role="img" aria-label="Scenario comparison chart showing baseline forecast versus scenario forecast with impact differences" />;
}
