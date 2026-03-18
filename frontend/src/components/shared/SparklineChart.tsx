import { useEffect, useRef, useState, useCallback } from "react";
import * as d3 from "d3";
import {
  type SparklineDataPoint,
  parsePoints,
  computeDimensions,
  setupScales,
  renderGridLines,
  renderXAxis,
  renderAreaFill,
  renderLines,
  setupTooltip,
} from "./sparklineChartHelpers";

export type { SparklineDataPoint };

interface SparklineChartProps {
  data: SparklineDataPoint[];
  forecast?: SparklineDataPoint[];
  height?: number;
}

export default function SparklineChart({
  data,
  forecast = [],
  height: containerHeight = 140,
}: SparklineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);

  // Responsive width tracking
  const updateWidth = useCallback(() => {
    if (containerRef.current) {
      setContainerWidth(containerRef.current.clientWidth);
    }
  }, []);

  useEffect(() => {
    updateWidth();
    const observer = new ResizeObserver(updateWidth);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [updateWidth]);

  useEffect(() => {
    if (!svgRef.current || containerWidth <= 0 || data.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const dims = computeDimensions(containerWidth, containerHeight);
    const historicalPoints = parsePoints(data);
    const forecastPoints = parsePoints(forecast);
    const allPoints = [...historicalPoints, ...forecastPoints];

    const g = svg
      .attr("width", dims.width)
      .attr("height", dims.height)
      .append("g")
      .attr("transform", `translate(${dims.margin.left},${dims.margin.top})`);

    const scales = setupScales(allPoints, dims);

    renderGridLines(g, scales, dims);
    renderXAxis(g, scales, dims);
    renderAreaFill(svg, g, historicalPoints, scales, dims);
    renderLines(g, historicalPoints, forecastPoints, scales);
    setupTooltip(svg, g, allPoints, scales, dims);

    return () => {
      if (svgRef.current) {
        d3.select(svgRef.current).selectAll("*").remove();
      }
    };
  }, [data, forecast, containerWidth, containerHeight]);

  return (
    <div ref={containerRef} className="w-full" style={{ height: containerHeight }}>
      {data.length === 0 ? (
        <div className="h-full flex items-center justify-center text-gray-400">
          <p className="text-sm">No data available</p>
        </div>
      ) : (
        <svg ref={svgRef} className="overflow-visible" role="img" aria-label="Sparkline trend chart showing data values over time" />
      )}
    </div>
  );
}
