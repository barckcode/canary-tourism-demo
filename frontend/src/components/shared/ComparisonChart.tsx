import { useEffect, useRef } from "react";
import * as d3 from "d3";
import { formatCompactNumber } from "../../utils/format";

export interface SeriesData {
  name: string;
  data: { period: string; value: number }[];
  color: string;
}

interface ComparisonChartProps {
  series: SeriesData[];
  width: number;
  height: number;
}

interface ParsedPoint {
  date: Date;
  value: number;
}

interface ParsedSeries {
  name: string;
  points: ParsedPoint[];
  color: string;
}

const MARGIN = { top: 24, right: 65, bottom: 40, left: 65 };

function parseSeries(series: SeriesData[]): ParsedSeries[] {
  return series.map((s) => ({
    name: s.name,
    color: s.color,
    points: s.data
      .map((d) => ({
        date: new Date(d.period + "-01"),
        value: d.value,
      }))
      .sort((a, b) => a.date.getTime() - b.date.getTime()),
  }));
}

export default function ComparisonChart({
  series,
  width,
  height,
}: ComparisonChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || width <= 0 || height <= 0 || series.length === 0)
      return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const parsed = parseSeries(series);
    const innerWidth = width - MARGIN.left - MARGIN.right;
    const innerHeight = height - MARGIN.top - MARGIN.bottom;

    const g = svg
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${MARGIN.left},${MARGIN.top})`);

    // Shared X scale across all series
    const allDates = parsed.flatMap((s) => s.points.map((p) => p.date));
    const xExtent = d3.extent(allDates) as [Date, Date];
    const x = d3.scaleTime().domain(xExtent).range([0, innerWidth]);

    // Create individual Y scales for each series
    const yScales = parsed.map((s) => {
      const vals = s.points.map((p) => p.value);
      const minVal = d3.min(vals) ?? 0;
      const maxVal = d3.max(vals) ?? 0;
      return d3
        .scaleLinear()
        .domain([Math.max(0, minVal * 0.9), maxVal * 1.05])
        .range([innerHeight, 0]);
    });

    // Grid lines (use first scale)
    g.append("g")
      .attr("class", "grid")
      .selectAll("line")
      .data(yScales[0].ticks(6))
      .join("line")
      .attr("x1", 0)
      .attr("x2", innerWidth)
      .attr("y1", (d) => yScales[0](d))
      .attr("y2", (d) => yScales[0](d))
      .attr("stroke", "rgba(255,255,255,0.05)")
      .attr("stroke-width", 1);

    // X axis
    g.append("g")
      .attr("transform", `translate(0,${innerHeight})`)
      .call(
        d3
          .axisBottom(x)
          .ticks(d3.timeYear.every(1))
          .tickFormat((d) => d3.timeFormat("%Y")(d as Date))
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

    // Left Y axis (first series)
    g.append("g")
      .call(
        d3
          .axisLeft(yScales[0])
          .ticks(6)
          .tickFormat((d) => formatCompactNumber(d as number))
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
          .attr("fill", parsed[0].color)
          .attr("font-size", "11px")
      );

    // Left Y axis label
    g.append("text")
      .attr("transform", "rotate(-90)")
      .attr("x", -innerHeight / 2)
      .attr("y", -50)
      .attr("text-anchor", "middle")
      .attr("fill", parsed[0].color)
      .attr("font-size", "10px")
      .text(parsed[0].name);

    // Right Y axis (second series, if exists and has different scale)
    if (parsed.length >= 2) {
      g.append("g")
        .attr("transform", `translate(${innerWidth},0)`)
        .call(
          d3
            .axisRight(yScales[1])
            .ticks(6)
            .tickFormat((d) => formatCompactNumber(d as number))
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
            .attr("fill", parsed[1].color)
            .attr("font-size", "11px")
        );

      // Right Y axis label
      g.append("text")
        .attr("transform", "rotate(90)")
        .attr("x", innerHeight / 2)
        .attr("y", -innerWidth - 50)
        .attr("text-anchor", "middle")
        .attr("fill", parsed[1].color)
        .attr("font-size", "10px")
        .text(parsed[1].name);
    }

    // Render lines
    parsed.forEach((s, i) => {
      const yScale = yScales[i];

      const line = d3
        .line<ParsedPoint>()
        .x((d) => x(d.date))
        .y((d) => yScale(d.value))
        .curve(d3.curveMonotoneX);

      g.append("path")
        .datum(s.points)
        .attr("d", line)
        .attr("fill", "none")
        .attr("stroke", s.color)
        .attr("stroke-width", 2);
    });

    // Tooltip
    const focus = g.append("g").style("display", "none");

    // One circle per series
    parsed.forEach((s) => {
      focus
        .append("circle")
        .attr("class", `dot-${s.name}`)
        .attr("r", 4)
        .attr("fill", s.color)
        .attr("stroke", "#fff")
        .attr("stroke-width", 1.5);
    });

    // Crosshair vertical line
    focus
      .append("line")
      .attr("class", "crosshair-x")
      .attr("stroke", "rgba(255,255,255,0.2)")
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "3,3");

    const tooltip = g
      .append("g")
      .attr("class", "tooltip-g")
      .style("display", "none");

    tooltip
      .append("rect")
      .attr("rx", 6)
      .attr("fill", "rgba(17,24,39,0.9)")
      .attr("stroke", "rgba(255,255,255,0.1)")
      .attr("stroke-width", 1);

    const tooltipDate = tooltip
      .append("text")
      .attr("fill", "rgba(255,255,255,0.6)")
      .attr("font-size", "10px");

    // One text line per series
    const tooltipLines = parsed.map((s, i) =>
      tooltip
        .append("text")
        .attr("fill", s.color)
        .attr("font-size", "11px")
        .attr("font-weight", "600")
        .attr("y", 32 + i * 16)
    );

    // Build bisector from first series dates
    const bisect = d3.bisector<ParsedPoint, Date>((d) => d.date).left;

    svg
      .append("rect")
      .attr("width", innerWidth)
      .attr("height", innerHeight)
      .attr("transform", `translate(${MARGIN.left},${MARGIN.top})`)
      .attr("fill", "transparent")
      .on("mouseover", () => {
        focus.style("display", null);
        tooltip.style("display", null);
      })
      .on("mouseout", () => {
        focus.style("display", "none");
        tooltip.style("display", "none");
      })
      .on("mousemove", (event) => {
        const [mx] = d3.pointer(event);
        const dateAtMouse = x.invert(mx);

        // Update each series dot
        parsed.forEach((s, i) => {
          const idx = Math.min(
            bisect(s.points, dateAtMouse),
            s.points.length - 1
          );
          const pt = s.points[idx];
          if (!pt) return;

          const cx = x(pt.date);
          const cy = yScales[i](pt.value);
          focus
            .select(`.dot-${s.name}`)
            .attr("cx", cx)
            .attr("cy", cy);
        });

        // Use first series for date reference
        const refIdx = Math.min(
          bisect(parsed[0].points, dateAtMouse),
          parsed[0].points.length - 1
        );
        const refPt = parsed[0].points[refIdx];
        if (!refPt) return;

        const cx = x(refPt.date);

        // Vertical crosshair
        focus
          .select(".crosshair-x")
          .attr("x1", cx)
          .attr("x2", cx)
          .attr("y1", 0)
          .attr("y2", innerHeight);

        const formattedDate = d3.timeFormat("%b %Y")(refPt.date);
        tooltipDate.text(formattedDate);

        // Update value text for each series
        parsed.forEach((s, i) => {
          const idx = Math.min(
            bisect(s.points, dateAtMouse),
            s.points.length - 1
          );
          const pt = s.points[idx];
          if (!pt) return;
          tooltipLines[i]
            .text(`${s.name}: ${formatCompactNumber(pt.value)}`)
            .attr("x", 8);
        });

        const tooltipW = 160;
        const tooltipH = 24 + parsed.length * 16;
        const tooltipX =
          cx + 12 > innerWidth - tooltipW ? cx - tooltipW - 12 : cx + 12;
        const tooltipY = Math.max(
          0,
          Math.min(
            innerHeight - tooltipH,
            yScales[0](refPt.value) - tooltipH / 2
          )
        );

        tooltip.attr("transform", `translate(${tooltipX},${tooltipY})`);
        tooltip
          .select("rect")
          .attr("width", tooltipW)
          .attr("height", tooltipH);
        tooltipDate.attr("x", 8).attr("y", 16);
      });

    // Legend at top
    const legend = g
      .append("g")
      .attr("transform", `translate(0,${-10})`);

    let legendX = 0;
    parsed.forEach((s) => {
      legend
        .append("line")
        .attr("x1", legendX)
        .attr("x2", legendX + 20)
        .attr("y1", 0)
        .attr("y2", 0)
        .attr("stroke", s.color)
        .attr("stroke-width", 2);

      const textEl = legend
        .append("text")
        .attr("x", legendX + 26)
        .attr("y", 4)
        .attr("fill", "rgba(255,255,255,0.5)")
        .attr("font-size", "10px")
        .text(s.name);

      const textLen = textEl.node()?.getComputedTextLength() ?? s.name.length * 6;
      legendX += 26 + textLen + 20;
    });

    return () => {
      if (svgRef.current) {
        d3.select(svgRef.current).selectAll("*").remove();
      }
    };
  }, [series, width, height]);

  const ariaLabel = series.map((s) => s.name).join(", ");

  return (
    <svg
      ref={svgRef}
      className="overflow-visible"
      role="img"
      aria-label={`Comparison chart showing ${ariaLabel}`}
    />
  );
}
