import { useEffect, useRef, useState, useCallback } from "react";
import * as d3 from "d3";

export interface SparklineDataPoint {
  period: string;
  value: number;
}

interface SparklineChartProps {
  data: SparklineDataPoint[];
  forecast?: SparklineDataPoint[];
  height?: number;
}

const MARGIN = { top: 8, right: 12, bottom: 20, left: 6 };

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

    const width = containerWidth;
    const height = containerHeight;
    const w = width - MARGIN.left - MARGIN.right;
    const h = height - MARGIN.top - MARGIN.bottom;

    const g = svg
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${MARGIN.left},${MARGIN.top})`);

    // Parse periods to dates
    const parsePeriod = (p: string) => {
      const [year, month] = p.split("-").map(Number);
      return new Date(year, month - 1, 1);
    };

    const historicalPoints = data.map((d) => ({
      date: parsePeriod(d.period),
      value: d.value,
    }));

    const forecastPoints = forecast.map((d) => ({
      date: parsePeriod(d.period),
      value: d.value,
    }));

    const allPoints = [...historicalPoints, ...forecastPoints];

    // Scales
    const x = d3
      .scaleTime()
      .domain(d3.extent(allPoints, (d) => d.date) as [Date, Date])
      .range([0, w]);

    const yExtent = d3.extent(allPoints, (d) => d.value) as [number, number];
    const yPadding = (yExtent[1] - yExtent[0]) * 0.15;
    const y = d3
      .scaleLinear()
      .domain([Math.max(0, yExtent[0] - yPadding), yExtent[1] + yPadding])
      .range([h, 0]);

    // Subtle grid lines (horizontal only)
    g.append("g")
      .selectAll("line")
      .data(y.ticks(3))
      .join("line")
      .attr("x1", 0)
      .attr("x2", w)
      .attr("y1", (d) => y(d))
      .attr("y2", (d) => y(d))
      .attr("stroke", "rgba(255,255,255,0.04)")
      .attr("stroke-width", 1);

    // X axis (minimal)
    g.append("g")
      .attr("transform", `translate(0,${h})`)
      .call(
        d3
          .axisBottom(x)
          .ticks(d3.timeMonth.every(6))
          .tickFormat((d) => d3.timeFormat("%b '%y")(d as Date))
          .tickSize(0)
      )
      .call((g) => g.select(".domain").remove())
      .call((g) =>
        g
          .selectAll(".tick text")
          .attr("fill", "rgba(255,255,255,0.3)")
          .attr("font-size", "9px")
          .attr("dy", "10px")
      );

    // Gradient definition for area fill
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

    // Area fill under historical line
    const area = d3
      .area<{ date: Date; value: number }>()
      .x((d) => x(d.date))
      .y0(h)
      .y1((d) => y(d.value))
      .curve(d3.curveMonotoneX);

    g.append("path")
      .datum(historicalPoints)
      .attr("d", area)
      .attr("fill", `url(#${gradientId})`);

    // Historical line
    const line = d3
      .line<{ date: Date; value: number }>()
      .x((d) => x(d.date))
      .y((d) => y(d.value))
      .curve(d3.curveMonotoneX);

    const historicalPath = g
      .append("path")
      .datum(historicalPoints)
      .attr("d", line)
      .attr("fill", "none")
      .attr("stroke", "#0ea5e9")
      .attr("stroke-width", 2)
      .attr("stroke-linecap", "round");

    // Animate line drawing
    const totalLength = historicalPath.node()?.getTotalLength() || 0;
    historicalPath
      .attr("stroke-dasharray", `${totalLength} ${totalLength}`)
      .attr("stroke-dashoffset", totalLength)
      .transition()
      .duration(1200)
      .ease(d3.easeCubicOut)
      .attr("stroke-dashoffset", 0);

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

      // Animate forecast after historical
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
        .attr("stroke-dasharray", `4 3`);
    }

    // Tooltip elements
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

    // Hover overlay
    const bisect = d3.bisector<{ date: Date; value: number }, Date>(
      (d) => d.date
    ).left;

    svg
      .append("rect")
      .attr("width", w)
      .attr("height", h)
      .attr("transform", `translate(${MARGIN.left},${MARGIN.top})`)
      .attr("fill", "transparent")
      .style("cursor", "crosshair")
      .on("mouseover", () => {
        focusDot.style("display", null);
        tooltipGroup.style("display", null);
      })
      .on("mouseout", () => {
        focusDot.style("display", "none");
        tooltipGroup.style("display", "none");
      })
      .on("mousemove", (event) => {
        const [mx] = d3.pointer(event);
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
        const formattedValue =
          d.value >= 1000000
            ? `${(d.value / 1000000).toFixed(1)}M`
            : d.value >= 1000
              ? `${(d.value / 1000).toFixed(0)}K`
              : `${d.value}`;

        tooltipPeriod.text(formattedDate);
        tooltipValue.text(formattedValue);

        const tooltipW = 72;
        const tooltipH = 36;
        const tooltipX =
          cx + 14 + tooltipW > w ? cx - tooltipW - 10 : cx + 14;
        const tooltipY = Math.max(0, Math.min(cy - tooltipH / 2, h - tooltipH));

        tooltipGroup.attr("transform", `translate(${tooltipX},${tooltipY})`);
        tooltipGroup.select("rect").attr("width", tooltipW).attr("height", tooltipH);
        tooltipPeriod.attr("x", 8).attr("y", 14);
        tooltipValue.attr("x", 8).attr("y", 28);
      });
  }, [data, forecast, containerWidth, containerHeight]);

  return (
    <div ref={containerRef} className="w-full" style={{ height: containerHeight }}>
      {data.length === 0 ? (
        <div className="h-full flex items-center justify-center text-gray-600">
          <p className="text-sm">No data available</p>
        </div>
      ) : (
        <svg ref={svgRef} className="overflow-visible" role="img" aria-label="Sparkline trend chart showing data values over time" />
      )}
    </div>
  );
}
