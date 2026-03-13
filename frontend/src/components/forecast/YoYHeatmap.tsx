import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";

interface YoYHeatmapProps {
  width: number;
  height: number;
}

interface CellData {
  year: number;
  month: number;
  arrivals: number;
  yoyChange: number | null;
}

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function generateMockHeatmapData(): CellData[] {
  const data: CellData[] = [];
  const baseValue = 500000;
  const seasonalPattern = [
    0.85, 0.82, 0.88, 0.9, 0.81, 0.83, 0.95, 0.92, 0.98, 1.1, 1.05, 1.0,
  ];

  const yearValues: Record<number, number[]> = {};

  for (let y = 2018; y <= 2026; y++) {
    yearValues[y] = [];
    for (let m = 0; m < 12; m++) {
      if (y === 2026 && m > 0) break;
      const trend = 1 + (y - 2018) * 0.03;
      const seasonal = seasonalPattern[m];
      const noise = 1 + (Math.random() - 0.5) * 0.06;
      let covidFactor = 1;
      if (y === 2020 && m >= 2) covidFactor = m < 6 ? 0.05 : 0.3 + m * 0.05;
      if (y === 2021 && m < 6) covidFactor = 0.5 + m * 0.08;

      const arrivals = Math.round(
        baseValue * trend * seasonal * noise * covidFactor
      );
      yearValues[y].push(arrivals);

      const prevYear = yearValues[y - 1];
      const yoyChange =
        prevYear && prevYear[m] !== undefined
          ? ((arrivals - prevYear[m]) / prevYear[m]) * 100
          : null;

      data.push({ year: y, month: m, arrivals, yoyChange });
    }
  }
  return data;
}

const MARGIN = { top: 30, right: 20, bottom: 10, left: 50 };

export default function YoYHeatmap({ width, height }: YoYHeatmapProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    data: CellData;
  } | null>(null);

  useEffect(() => {
    if (!svgRef.current || width <= 0 || height <= 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const data = generateMockHeatmapData();
    const years = [...new Set(data.map((d) => d.year))].sort();

    const w = width - MARGIN.left - MARGIN.right;
    const h = height - MARGIN.top - MARGIN.bottom;

    const g = svg
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${MARGIN.left},${MARGIN.top})`);

    const cellW = w / 12;
    const cellH = h / years.length;

    // Color scale: red (negative) → neutral → blue (positive)
    const colorScale = d3
      .scaleLinear<string>()
      .domain([-50, 0, 50])
      .range(["#ef4444", "rgba(255,255,255,0.05)", "#0087b9"])
      .clamp(true);

    // Month labels (top)
    g.selectAll(".month-label")
      .data(MONTHS)
      .join("text")
      .attr("x", (_d, i) => i * cellW + cellW / 2)
      .attr("y", -10)
      .attr("text-anchor", "middle")
      .attr("fill", "rgba(255,255,255,0.4)")
      .attr("font-size", "10px")
      .text((d) => d);

    // Year labels (left)
    g.selectAll(".year-label")
      .data(years)
      .join("text")
      .attr("x", -8)
      .attr("y", (_d, i) => i * cellH + cellH / 2)
      .attr("text-anchor", "end")
      .attr("dominant-baseline", "middle")
      .attr("fill", "rgba(255,255,255,0.4)")
      .attr("font-size", "11px")
      .text((d) => d);

    // Cells
    g.selectAll(".cell")
      .data(data)
      .join("rect")
      .attr("x", (d) => d.month * cellW + 1)
      .attr("y", (d) => years.indexOf(d.year) * cellH + 1)
      .attr("width", cellW - 2)
      .attr("height", cellH - 2)
      .attr("rx", 3)
      .attr("fill", (d) =>
        d.yoyChange !== null ? colorScale(d.yoyChange) : "rgba(255,255,255,0.03)"
      )
      .attr("stroke", "rgba(255,255,255,0.05)")
      .attr("stroke-width", 0.5)
      .attr("cursor", "pointer")
      .on("mouseenter", function (event, d) {
        d3.select(this).attr("stroke", "rgba(255,255,255,0.4)").attr("stroke-width", 1.5);
        const rect = (event.target as SVGRectElement).getBoundingClientRect();
        const svgRect = svgRef.current!.getBoundingClientRect();
        setTooltip({
          x: rect.left - svgRect.left + rect.width / 2,
          y: rect.top - svgRect.top - 8,
          data: d,
        });
      })
      .on("mouseleave", function () {
        d3.select(this).attr("stroke", "rgba(255,255,255,0.05)").attr("stroke-width", 0.5);
        setTooltip(null);
      });

    // Cell text (YoY % for non-null)
    g.selectAll(".cell-text")
      .data(data.filter((d) => d.yoyChange !== null))
      .join("text")
      .attr("x", (d) => d.month * cellW + cellW / 2)
      .attr("y", (d) => years.indexOf(d.year) * cellH + cellH / 2)
      .attr("text-anchor", "middle")
      .attr("dominant-baseline", "middle")
      .attr("fill", (d) =>
        Math.abs(d.yoyChange!) > 20
          ? "rgba(255,255,255,0.9)"
          : "rgba(255,255,255,0.5)"
      )
      .attr("font-size", cellW > 50 ? "10px" : "8px")
      .attr("font-weight", (d) => (Math.abs(d.yoyChange!) > 20 ? "600" : "400"))
      .attr("pointer-events", "none")
      .text((d) =>
        d.yoyChange !== null
          ? `${d.yoyChange > 0 ? "+" : ""}${d.yoyChange.toFixed(0)}%`
          : ""
      );
  }, [width, height]);

  return (
    <div className="relative">
      <svg ref={svgRef} className="overflow-visible" />
      {tooltip && (
        <div
          className="absolute pointer-events-none z-10 glass-panel px-3 py-2 text-xs -translate-x-1/2 -translate-y-full"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          <div className="font-semibold text-white">
            {MONTHS[tooltip.data.month]} {tooltip.data.year}
          </div>
          <div className="text-gray-400 mt-0.5">
            Arrivals:{" "}
            <span className="text-gray-200">
              {(tooltip.data.arrivals / 1000).toFixed(0)}K
            </span>
          </div>
          {tooltip.data.yoyChange !== null && (
            <div
              className={`mt-0.5 font-medium ${
                tooltip.data.yoyChange > 0
                  ? "text-tropical-400"
                  : tooltip.data.yoyChange < 0
                    ? "text-red-400"
                    : "text-gray-400"
              }`}
            >
              YoY: {tooltip.data.yoyChange > 0 ? "+" : ""}
              {tooltip.data.yoyChange.toFixed(1)}%
            </div>
          )}
        </div>
      )}
    </div>
  );
}
