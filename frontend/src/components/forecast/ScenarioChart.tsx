import { useEffect, useRef, useMemo } from "react";
import * as d3 from "d3";
import {
  type ScenarioPoint,
  type ScenarioResultData,
  computeDimensions,
  parseScenarioData,
  setupScales,
  renderGridLines,
  renderAxes,
  renderAreas,
  renderLines,
  setupTooltip,
  renderLegend,
} from "./scenarioChartHelpers";

export type { ScenarioPoint, ScenarioResultData };

interface ScenarioChartProps {
  data: ScenarioResultData;
  width: number;
  height: number;
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

    const dims = computeDimensions(width, height);
    const { baselineData, scenarioData, combinedData } = parseScenarioData(data);
    if (baselineData.length === 0) return;

    const g = svg
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${dims.margin.left},${dims.margin.top})`);

    const scales = setupScales(baselineData, scenarioData, dims);

    renderGridLines(g, scales, dims);
    renderAxes(g, scales, dims);
    renderAreas(g, combinedData, scales);
    renderLines(g, baselineData, scenarioData, scales);
    setupTooltip(svg, g, combinedData, scales, dims);
    renderLegend(g, dims);
  }, [data, width, height]);

  return <svg ref={svgRef} className="overflow-visible" role="img" aria-label="Scenario comparison chart showing baseline forecast versus scenario forecast with impact differences" />;
}
