import * as d3 from "d3";
import { formatCompactNumber } from "../../utils/format";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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

export interface DataPointWithType {
  date: Date;
  value: number;
  isForecast: boolean;
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

export const MARGIN = { top: 20, right: 30, bottom: 40, left: 65 };

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

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
  historical: TimeSeriesPoint[],
  forecast: ForecastPoint[],
  dims: Dimensions
): Scales {
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
    .range([0, dims.innerWidth]);

  const y = d3
    .scaleLinear()
    .domain([
      Math.max(0, (d3.min(allValues) || 0) * 0.9),
      (d3.max(allValues) || 0) * 1.05,
    ])
    .range([dims.innerHeight, 0]);

  return { x, y };
}

// ---------------------------------------------------------------------------
// Rendering helpers
// ---------------------------------------------------------------------------

export function renderGridLines(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  scales: Scales,
  dims: Dimensions
): void {
  g.append("g")
    .attr("class", "grid")
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
  dims: Dimensions,
  yLabel: string
): void {
  // X axis
  g.append("g")
    .attr("transform", `translate(0,${dims.innerHeight})`)
    .call(
      d3
        .axisBottom(scales.x)
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

  // Y axis
  g.append("g")
    .call(
      d3
        .axisLeft(scales.y)
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
    .text(yLabel);
}

export function renderConfidenceBands(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  forecast: ForecastPoint[],
  scales: Scales
): void {
  if (forecast.length === 0) return;

  // 95% confidence band
  const area95 = d3
    .area<ForecastPoint>()
    .x((d) => scales.x(d.date))
    .y0((d) => scales.y(d.ci95Lower))
    .y1((d) => scales.y(d.ci95Upper))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(forecast)
    .attr("d", area95)
    .attr("fill", "rgba(0, 135, 185, 0.08)")
    .attr("stroke", "none");

  // 80% confidence band
  const area80 = d3
    .area<ForecastPoint>()
    .x((d) => scales.x(d.date))
    .y0((d) => scales.y(d.ci80Lower))
    .y1((d) => scales.y(d.ci80Upper))
    .curve(d3.curveMonotoneX);

  g.append("path")
    .datum(forecast)
    .attr("d", area80)
    .attr("fill", "rgba(0, 135, 185, 0.15)")
    .attr("stroke", "none");
}

export function renderDividerLine(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  historical: TimeSeriesPoint[],
  forecast: ForecastPoint[],
  scales: Scales,
  dims: Dimensions
): void {
  if (historical.length === 0 || forecast.length === 0) return;

  const dividerX = scales.x(historical[historical.length - 1].date);
  g.append("line")
    .attr("x1", dividerX)
    .attr("x2", dividerX)
    .attr("y1", 0)
    .attr("y2", dims.innerHeight)
    .attr("stroke", "rgba(255,255,255,0.15)")
    .attr("stroke-width", 1)
    .attr("stroke-dasharray", "4,4");
}

export function renderLines(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  historical: TimeSeriesPoint[],
  forecast: ForecastPoint[],
  scales: Scales
): void {
  const line = d3
    .line<TimeSeriesPoint>()
    .x((d) => scales.x(d.date))
    .y((d) => scales.y(d.value))
    .curve(d3.curveMonotoneX);

  // Historical line
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
      .x((d) => scales.x(d.date))
      .y((d) => scales.y(d.value))
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
}

export function setupTooltip(
  svg: d3.Selection<SVGSVGElement, unknown, null, undefined>,
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  historical: TimeSeriesPoint[],
  forecast: ForecastPoint[],
  scales: Scales,
  dims: Dimensions,
  isMock: boolean
): void {
  const { x, y } = scales;
  const { innerWidth: w, innerHeight: h } = dims;

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

  const tooltipType = tooltip.append("text").attr("font-size", "9px");

  const allDataPoints: DataPointWithType[] = [
    ...historical.map((d) => ({
      date: d.date,
      value: d.value,
      isForecast: false,
    })),
    ...forecast.map((d) => ({
      date: d.date,
      value: d.value,
      isForecast: true,
    })),
  ];

  const bisect = d3.bisector<DataPointWithType, Date>((d) => d.date).left;

  svg
    .append("rect")
    .attr("width", w)
    .attr("height", h)
    .attr("transform", `translate(${dims.margin.left},${dims.margin.top})`)
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
      const formattedValue = formatCompactNumber(d.value);

      let typeLabel: string;
      let typeColor: string;
      if (isMock) {
        typeLabel = "DEMO";
        typeColor = "rgba(245, 158, 11, 0.8)";
      } else if (d.isForecast) {
        typeLabel = "Forecast";
        typeColor = "rgba(40, 192, 102, 0.8)";
      } else {
        typeLabel = "Actual";
        typeColor = "rgba(0, 135, 185, 0.8)";
      }

      tooltipDate.text(formattedDate);
      tooltipValue.text(formattedValue);
      tooltipType.text(typeLabel).attr("fill", typeColor);

      const tooltipW = 90;
      const tooltipH = 54;
      const tooltipX =
        cx + 12 > w - tooltipW ? cx - tooltipW - 12 : cx + 12;
      const tooltipY = cy - tooltipH / 2;

      tooltip.attr("transform", `translate(${tooltipX},${tooltipY})`);
      tooltip
        .select("rect")
        .attr("width", tooltipW)
        .attr("height", tooltipH);
      tooltipDate.attr("x", 8).attr("y", 16);
      tooltipValue.attr("x", 8).attr("y", 32);
      tooltipType.attr("x", 8).attr("y", 46);
    });
}

export function renderLegend(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  dims: Dimensions
): void {
  const legend = g
    .append("g")
    .attr("transform", `translate(${dims.innerWidth - 200},${-5})`);

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
}
