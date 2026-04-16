import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import * as d3 from "d3";
import { useYoYHeatmap, type YoYCell } from "../../api/hooks";
import { setupTooltipKeyboardDismiss } from "../../utils/chartAccessibility";

interface YoYHeatmapProps {
  width: number;
  height: number;
}

interface CellData {
  year: number;
  month: number;
  value: number;
  yoyChange: number | null;
}

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const MARGIN = { top: 30, right: 20, bottom: 10, left: 50 };

/**
 * Convert API YoY cells into the flat CellData array used by the D3 chart.
 * When multiple indicators are returned, we use the first one (turistas by
 * default since it is first in the backend list).
 */
function apiToCellData(indicators: Record<string, YoYCell[]>): CellData[] {
  const keys = Object.keys(indicators);
  if (keys.length === 0) return [];

  // Prefer "turistas" if available, otherwise use the first indicator
  const key = keys.includes("turistas") ? "turistas" : keys[0];
  const cells = indicators[key];

  return cells.map((c) => ({
    year: c.year,
    month: c.month,
    value: c.value,
    yoyChange: c.yoy_change,
  }));
}

export default function YoYHeatmap({ width, height }: YoYHeatmapProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const { t } = useTranslation();
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    data: CellData;
  } | null>(null);

  const { data: yoyData, loading, error } = useYoYHeatmap();

  const cellData = yoyData ? apiToCellData(yoyData.indicators) : [];

  useEffect(() => {
    if (!svgRef.current || width <= 0 || height <= 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.append("title").text(t('accessibility.yoyHeatmap'));

    if (cellData.length === 0) return;

    const data = cellData;
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

    // Color scale: red (negative) -> neutral -> blue (positive)
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

    // Touch support for heatmap cells
    g.selectAll<SVGRectElement, CellData>(".cell")
      .each(function () {
        const node = this;
        node.addEventListener(
          "touchstart",
          (event: TouchEvent) => {
            event.preventDefault();
            d3.select(node).attr("stroke", "rgba(255,255,255,0.4)").attr("stroke-width", 1.5);
            const cellRect = node.getBoundingClientRect();
            const svgRect = svgRef.current!.getBoundingClientRect();
            const d = d3.select<SVGRectElement, CellData>(node).datum();
            setTooltip({
              x: cellRect.left - svgRect.left + cellRect.width / 2,
              y: cellRect.top - svgRect.top - 8,
              data: d,
            });
          },
          { passive: false }
        );
        node.addEventListener("touchend", () => {
          d3.select(node).attr("stroke", "rgba(255,255,255,0.05)").attr("stroke-width", 0.5);
          setTooltip(null);
        });
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

    // ESC key dismiss for keyboard accessibility (WCAG 1.4.13)
    const cleanupEsc = setupTooltipKeyboardDismiss(svgRef.current, () => setTooltip(null));

    return () => {
      cleanupEsc();
      if (svgRef.current) {
        d3.select(svgRef.current).selectAll("*").remove();
      }
    };
  }, [width, height, cellData, t]);

  // Loading state
  if (loading) {
    return (
      <div
        className="animate-pulse space-y-4 p-4"
        style={{ width, height }}
        role="status"
        aria-live="polite"
        aria-label={t('common.loading')}
      >
        <div className="h-6 bg-white/10 rounded w-1/4"></div>
        <div className="flex-1 h-48 bg-white/10 rounded"></div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div
        className="flex items-center justify-center"
        style={{ width, height }}
      >
        <div className="text-center">
          <p className="text-red-400 text-sm font-medium">
            Failed to load heatmap data
          </p>
          <p className="text-gray-400 text-xs mt-1">{error}</p>
        </div>
      </div>
    );
  }

  // Empty state - not enough data
  if (cellData.length === 0) {
    return (
      <div
        className="flex items-center justify-center"
        style={{ width, height }}
      >
        <div className="text-center">
          <p className="text-gray-400 text-sm font-medium">
            Not enough data for YoY comparison
          </p>
          <p className="text-gray-400 text-xs mt-1">
            At least two years of monthly data are required to calculate
            year-over-year changes.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative">
      <svg ref={svgRef} className="overflow-visible" role="img" aria-label={t('accessibility.yoyHeatmap')} tabIndex={0} />
      {tooltip && (
        <div
          className="absolute pointer-events-none z-10 glass-panel px-3 py-2 text-xs -translate-x-1/2 -translate-y-full"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          <div className="font-semibold text-white">
            {MONTHS[tooltip.data.month]} {tooltip.data.year}
          </div>
          <div className="text-gray-400 mt-0.5">
            Value:{" "}
            <span className="text-gray-200">
              {tooltip.data.value >= 1000
                ? `${(tooltip.data.value / 1000).toFixed(0)}K`
                : tooltip.data.value.toLocaleString()}
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
