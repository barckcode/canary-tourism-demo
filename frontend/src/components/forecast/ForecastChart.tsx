import { useEffect, useRef } from "react";
import * as d3 from "d3";

export interface TimeSeriesPoint {
  date: Date;
  value: number;
}

export interface ForecastPoint {
  date: Date;
  value: number;
  ci80Lower: number;
  ci80Upper: number;
  ci95Lower: number;
  ci95Upper: number;
}

interface ForecastChartProps {
  historical: TimeSeriesPoint[];
  forecast: ForecastPoint[];
  width: number;
  height: number;
  yLabel?: string;
}

// Mock data generator
export function generateMockData(): {
  historical: TimeSeriesPoint[];
  forecast: ForecastPoint[];
} {
  const historical: TimeSeriesPoint[] = [];
  const forecast: ForecastPoint[] = [];

  // Historical: 2018-01 to 2026-01 (monthly)
  const baseValue = 500000;
  const seasonalPattern = [
    0.85, 0.82, 0.88, 0.9, 0.81, 0.83, 0.95, 0.92, 0.98, 1.1, 1.05, 1.0,
  ];

  for (let y = 2018; y <= 2025; y++) {
    for (let m = 0; m < 12; m++) {
      if (y === 2025 && m > 11) break;
      const trend = 1 + (y - 2018) * 0.03;
      const seasonal = seasonalPattern[m];
      const noise = 1 + (Math.random() - 0.5) * 0.08;

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
  const lastHistValue = historical[historical.length - 1].value;
  for (let m = 1; m <= 12; m++) {
    const monthIdx = (m + 0) % 12;
    const seasonal = seasonalPattern[monthIdx];
    const trend = 1 + m * 0.002;
    const value = Math.round(lastHistValue * seasonal * trend);
    const spread80 = value * 0.06 * Math.sqrt(m);
    const spread95 = value * 0.1 * Math.sqrt(m);

    forecast.push({
      date: new Date(2026, m, 1),
      value,
      ci80Lower: Math.round(value - spread80),
      ci80Upper: Math.round(value + spread80),
      ci95Lower: Math.round(value - spread95),
      ci95Upper: Math.round(value + spread95),
    });
  }

  return { historical, forecast };
}

const MARGIN = { top: 20, right: 30, bottom: 40, left: 65 };

export default function ForecastChart({
  historical,
  forecast,
  width,
  height,
  yLabel = "Tourist Arrivals",
}: ForecastChartProps) {
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

    // Combined data for scales
    const allDates = [
      ...historical.map((d) => d.date),
      ...forecast.map((d) => d.date),
    ];
    const allValues = [
      ...historical.map((d) => d.value),
      ...forecast.flatMap((d) => [d.ci95Lower, d.ci95Upper]),
    ];

    const x = d3
      .scaleTime()
      .domain(d3.extent(allDates) as [Date, Date])
      .range([0, w]);

    const y = d3
      .scaleLinear()
      .domain([
        Math.max(0, (d3.min(allValues) || 0) * 0.9),
        (d3.max(allValues) || 0) * 1.05,
      ])
      .range([h, 0]);

    // Grid lines
    g.append("g")
      .attr("class", "grid")
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
          .ticks(d3.timeYear.every(1))
          .tickFormat((d) => d3.timeFormat("%Y")(d as Date))
      )
      .call((g) => g.select(".domain").attr("stroke", "rgba(255,255,255,0.1)"))
      .call((g) =>
        g.selectAll(".tick line").attr("stroke", "rgba(255,255,255,0.1)")
      )
      .call((g) =>
        g.selectAll(".tick text").attr("fill", "rgba(255,255,255,0.4)").attr("font-size", "11px")
      );

    // Y axis
    g.append("g")
      .call(
        d3
          .axisLeft(y)
          .ticks(6)
          .tickFormat((d) => {
            const val = d as number;
            return val >= 1000000
              ? `${(val / 1000000).toFixed(1)}M`
              : val >= 1000
                ? `${(val / 1000).toFixed(0)}K`
                : `${val}`;
          })
      )
      .call((g) => g.select(".domain").attr("stroke", "rgba(255,255,255,0.1)"))
      .call((g) =>
        g.selectAll(".tick line").attr("stroke", "rgba(255,255,255,0.1)")
      )
      .call((g) =>
        g.selectAll(".tick text").attr("fill", "rgba(255,255,255,0.4)").attr("font-size", "11px")
      );

    // Y axis label
    g.append("text")
      .attr("transform", "rotate(-90)")
      .attr("x", -h / 2)
      .attr("y", -50)
      .attr("text-anchor", "middle")
      .attr("fill", "rgba(255,255,255,0.3)")
      .attr("font-size", "11px")
      .text(yLabel);

    // 95% confidence band
    if (forecast.length > 0) {
      const area95 = d3
        .area<ForecastPoint>()
        .x((d) => x(d.date))
        .y0((d) => y(d.ci95Lower))
        .y1((d) => y(d.ci95Upper))
        .curve(d3.curveMonotoneX);

      g.append("path")
        .datum(forecast)
        .attr("d", area95)
        .attr("fill", "rgba(0, 135, 185, 0.08)")
        .attr("stroke", "none");

      // 80% confidence band
      const area80 = d3
        .area<ForecastPoint>()
        .x((d) => x(d.date))
        .y0((d) => y(d.ci80Lower))
        .y1((d) => y(d.ci80Upper))
        .curve(d3.curveMonotoneX);

      g.append("path")
        .datum(forecast)
        .attr("d", area80)
        .attr("fill", "rgba(0, 135, 185, 0.15)")
        .attr("stroke", "none");
    }

    // Divider line between historical and forecast
    if (historical.length > 0 && forecast.length > 0) {
      const dividerX = x(historical[historical.length - 1].date);
      g.append("line")
        .attr("x1", dividerX)
        .attr("x2", dividerX)
        .attr("y1", 0)
        .attr("y2", h)
        .attr("stroke", "rgba(255,255,255,0.15)")
        .attr("stroke-width", 1)
        .attr("stroke-dasharray", "4,4");
    }

    // Historical line
    const line = d3
      .line<TimeSeriesPoint>()
      .x((d) => x(d.date))
      .y((d) => y(d.value))
      .curve(d3.curveMonotoneX);

    g.append("path")
      .datum(historical)
      .attr("d", line)
      .attr("fill", "none")
      .attr("stroke", "#0087b9")
      .attr("stroke-width", 2);

    // Forecast line (dashed)
    if (forecast.length > 0) {
      const bridgeData: TimeSeriesPoint[] = [
        historical[historical.length - 1],
        { date: forecast[0].date, value: forecast[0].value },
      ];

      const forecastLine = d3
        .line<{ date: Date; value: number }>()
        .x((d) => x(d.date))
        .y((d) => y(d.value))
        .curve(d3.curveMonotoneX);

      // Bridge segment
      g.append("path")
        .datum(bridgeData)
        .attr("d", forecastLine)
        .attr("fill", "none")
        .attr("stroke", "#28c066")
        .attr("stroke-width", 2)
        .attr("stroke-dasharray", "6,4");

      // Forecast segment
      g.append("path")
        .datum(forecast.map((d) => ({ date: d.date, value: d.value })))
        .attr("d", forecastLine)
        .attr("fill", "none")
        .attr("stroke", "#28c066")
        .attr("stroke-width", 2)
        .attr("stroke-dasharray", "6,4");
    }

    // Tooltip dot + crosshair
    const focus = g.append("g").style("display", "none");

    focus
      .append("circle")
      .attr("r", 4)
      .attr("fill", "#0087b9")
      .attr("stroke", "#fff")
      .attr("stroke-width", 1.5);

    focus
      .append("line")
      .attr("class", "crosshair-y")
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

    const tooltipValue = tooltip
      .append("text")
      .attr("fill", "#fff")
      .attr("font-size", "12px")
      .attr("font-weight", "600");

    // Hover overlay
    const allDataPoints = [
      ...historical.map((d) => ({ date: d.date, value: d.value })),
      ...forecast.map((d) => ({ date: d.date, value: d.value })),
    ];

    const bisect = d3.bisector<{ date: Date; value: number }, Date>(
      (d) => d.date
    ).left;

    svg
      .append("rect")
      .attr("width", w)
      .attr("height", h)
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
        const idx = Math.min(
          bisect(allDataPoints, dateAtMouse),
          allDataPoints.length - 1
        );
        const d = allDataPoints[idx];
        if (!d) return;

        const cx = x(d.date);
        const cy = y(d.value);

        focus.attr("transform", `translate(${cx},${cy})`);
        focus
          .select(".crosshair-y")
          .attr("x1", -cx)
          .attr("x2", w - cx)
          .attr("y1", 0)
          .attr("y2", 0);

        const formattedDate = d3.timeFormat("%b %Y")(d.date);
        const formattedValue =
          d.value >= 1000 ? `${(d.value / 1000).toFixed(0)}K` : `${d.value}`;

        tooltipDate.text(formattedDate);
        tooltipValue.text(formattedValue);

        const tooltipW = 90;
        const tooltipH = 42;
        const tooltipX = cx + 12 > w - tooltipW ? cx - tooltipW - 12 : cx + 12;
        const tooltipY = cy - tooltipH / 2;

        tooltip.attr("transform", `translate(${tooltipX},${tooltipY})`);
        tooltip.select("rect").attr("width", tooltipW).attr("height", tooltipH);
        tooltipDate.attr("x", 8).attr("y", 16);
        tooltipValue.attr("x", 8).attr("y", 34);
      });

    // Legend
    const legend = g
      .append("g")
      .attr("transform", `translate(${w - 200},${-5})`);

    // Historical legend
    legend
      .append("line")
      .attr("x1", 0)
      .attr("x2", 20)
      .attr("y1", 0)
      .attr("y2", 0)
      .attr("stroke", "#0087b9")
      .attr("stroke-width", 2);
    legend
      .append("text")
      .attr("x", 26)
      .attr("y", 4)
      .attr("fill", "rgba(255,255,255,0.5)")
      .attr("font-size", "10px")
      .text("Historical");

    // Forecast legend
    legend
      .append("line")
      .attr("x1", 90)
      .attr("x2", 110)
      .attr("y1", 0)
      .attr("y2", 0)
      .attr("stroke", "#28c066")
      .attr("stroke-width", 2)
      .attr("stroke-dasharray", "6,4");
    legend
      .append("text")
      .attr("x", 116)
      .attr("y", 4)
      .attr("fill", "rgba(255,255,255,0.5)")
      .attr("font-size", "10px")
      .text("Forecast");
  }, [historical, forecast, width, height, yLabel]);

  return <svg ref={svgRef} className="overflow-visible" />;
}
