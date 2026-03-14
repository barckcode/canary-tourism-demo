import { useEffect, useRef } from "react";
import * as d3 from "d3";
import {
  type TimeSeriesPoint,
  type ForecastPoint,
  computeDimensions,
  setupScales,
  renderGridLines,
  renderAxes,
  renderConfidenceBands,
  renderDividerLine,
  renderLines,
  setupTooltip,
  renderLegend,
} from "./forecastChartHelpers";

export type { TimeSeriesPoint, ForecastPoint };

interface ForecastChartProps {
  historical: TimeSeriesPoint[];
  forecast: ForecastPoint[];
  width: number;
  height: number;
  yLabel?: string;
  isMock?: boolean;
}

// Mock data generator with deterministic seed for consistency
export function generateMockData(): {
  historical: TimeSeriesPoint[];
  forecast: ForecastPoint[];
} {
  const historical: TimeSeriesPoint[] = [];
  const forecast: ForecastPoint[] = [];

  // Historical: 2018-01 to 2026-01 (monthly)
  const baseValue = 500000;
  // Index 0=Jan, 1=Feb, ..., 9=Oct (peak), 11=Dec
  const seasonalPattern = [
    0.85, 0.82, 0.88, 0.9, 0.81, 0.83, 0.95, 0.92, 0.98, 1.1, 1.05, 1.0,
  ];

  // Simple seeded PRNG for deterministic mock data
  let seed = 42;
  const seededRandom = () => {
    seed = (seed * 16807 + 0) % 2147483647;
    return (seed - 1) / 2147483646;
  };

  // Historical through January 2026
  for (let y = 2018; y <= 2026; y++) {
    const lastMonth = y === 2026 ? 0 : 11; // Jan only for 2026
    for (let m = 0; m <= lastMonth; m++) {
      const trend = 1 + (y - 2018) * 0.03;
      const seasonal = seasonalPattern[m];
      const noise = 1 + (seededRandom() - 0.5) * 0.08;

      // COVID dip
      let covidFactor = 1;
      if (y === 2020 && m >= 2) covidFactor = m < 6 ? 0.05 : 0.3 + m * 0.05;
      if (y === 2021 && m < 6) covidFactor = 0.5 + m * 0.08;

      historical.push({
        date: new Date(y, m, 1),
        value: Math.round(baseValue * trend * seasonal * noise * covidFactor),
      });
    }
  }

  // Forecast: 2026-02 to 2027-01 (12 months)
  // Use a deseasonalized base to avoid double-applying seasonal factors
  const lastHistValue = historical[historical.length - 1].value;
  const lastHistSeasonal = seasonalPattern[0]; // January
  const deseasonalizedBase = lastHistValue / lastHistSeasonal;

  for (let i = 0; i < 12; i++) {
    const forecastMonth = (1 + i) % 12; // Feb=1, Mar=2, ..., Jan=0
    const seasonal = seasonalPattern[forecastMonth];
    const trend = 1 + (i + 1) * 0.002;
    const value = Math.round(deseasonalizedBase * seasonal * trend);
    const spread80 = value * 0.06 * Math.sqrt(i + 1);
    const spread95 = value * 0.1 * Math.sqrt(i + 1);

    // Date: Feb 2026 (i=0) through Jan 2027 (i=11)
    const year = i < 11 ? 2026 : 2027;
    const month = (1 + i) % 12;

    forecast.push({
      date: new Date(year, month, 1),
      value,
      ci80Lower: Math.round(value - spread80),
      ci80Upper: Math.round(value + spread80),
      ci95Lower: Math.round(value - spread95),
      ci95Upper: Math.round(value + spread95),
    });
  }

  return { historical, forecast };
}

export default function ForecastChart({
  historical,
  forecast,
  width,
  height,
  yLabel = "Tourist Arrivals",
  isMock = false,
}: ForecastChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || width <= 0 || height <= 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const dims = computeDimensions(width, height);

    const g = svg
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${dims.margin.left},${dims.margin.top})`);

    const scales = setupScales(historical, forecast, dims);

    renderGridLines(g, scales, dims);
    renderAxes(g, scales, dims, yLabel);
    renderConfidenceBands(g, forecast, scales);
    renderDividerLine(g, historical, forecast, scales, dims);
    renderLines(g, historical, forecast, scales);
    setupTooltip(svg, g, historical, forecast, scales, dims, isMock);
    renderLegend(g, dims);
  }, [historical, forecast, width, height, yLabel, isMock]);

  return <svg ref={svgRef} className="overflow-visible" role="img" aria-label={`${yLabel} forecast chart showing historical data and predicted values with confidence intervals`} />;
}
