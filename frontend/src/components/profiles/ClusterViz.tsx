import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";

export interface ClusterData {
  id: number;
  name: string;
  sizePct: number;
  avgAge: number;
  avgSpend: number;
  avgNights: number;
  color: string;
  description: string;
}

interface ClusterVizProps {
  width: number;
  height: number;
  clusters?: ClusterData[];
  onSelect?: (cluster: ClusterData | null) => void;
}

const DEFAULT_CLUSTERS: ClusterData[] = [
  {
    id: 0,
    name: "Budget Young",
    sizePct: 47,
    avgAge: 28,
    avgSpend: 350,
    avgNights: 5,
    color: "#0087b9",
    description: "Young travelers, apartments, low-cost flights",
  },
  {
    id: 1,
    name: "High Spender",
    sizePct: 15,
    avgAge: 52,
    avgSpend: 1200,
    avgNights: 8,
    color: "#f69b1a",
    description: "Families, 4-star hotels, excursions & dining",
  },
  {
    id: 2,
    name: "Budget Older",
    sizePct: 34,
    avgAge: 65,
    avgSpend: 400,
    avgNights: 7,
    color: "#28c066",
    description: "Retirees, package holidays, relaxation focus",
  },
  {
    id: 3,
    name: "Premium VIP",
    sizePct: 1,
    avgAge: 45,
    avgSpend: 2500,
    avgNights: 14,
    color: "#a855f7",
    description: "Luxury segment, villas, high activity level",
  },
];

const MARGIN = 20;

export default function ClusterViz({
  width,
  height,
  clusters = DEFAULT_CLUSTERS,
  onSelect,
}: ClusterVizProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [selected, setSelected] = useState<number | null>(null);

  useEffect(() => {
    if (!svgRef.current || width <= 0 || height <= 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    svg.attr("width", width).attr("height", height);

    const cx = width / 2;
    const cy = height / 2;
    const maxRadius = Math.min(width, height) / 2 - MARGIN;

    // Scale bubble radius by sqrt of percentage
    const radiusScale = d3
      .scaleSqrt()
      .domain([0, d3.max(clusters, (d) => d.sizePct) || 50])
      .range([20, maxRadius * 0.55]);

    // Prepare simulation nodes
    interface SimNode extends d3.SimulationNodeDatum {
      cluster: ClusterData;
      r: number;
    }

    const nodes: SimNode[] = clusters.map((c) => ({
      cluster: c,
      r: radiusScale(c.sizePct),
      x: cx + (Math.random() - 0.5) * 50,
      y: cy + (Math.random() - 0.5) * 50,
    }));

    // Force simulation
    const simulation = d3
      .forceSimulation(nodes)
      .force("x", d3.forceX(cx).strength(0.05))
      .force("y", d3.forceY(cy).strength(0.05))
      .force(
        "collision",
        d3.forceCollide<SimNode>().radius((d) => d.r + 4).strength(0.8)
      )
      .force("charge", d3.forceManyBody().strength(-30))
      .stop();

    // Run simulation synchronously
    for (let i = 0; i < 200; i++) simulation.tick();

    // Draw bubbles
    const bubbleGroup = svg
      .selectAll<SVGGElement, SimNode>(".bubble")
      .data(nodes)
      .join("g")
      .attr("class", "bubble")
      .attr("transform", (d) => `translate(${d.x},${d.y})`)
      .attr("cursor", "pointer")
      .on("click", (_event, d) => {
        const newId = selected === d.cluster.id ? null : d.cluster.id;
        setSelected(newId);
        onSelect?.(newId !== null ? d.cluster : null);
      });

    // Glow filter
    const defs = svg.append("defs");
    clusters.forEach((c) => {
      const filter = defs
        .append("filter")
        .attr("id", `glow-${c.id}`)
        .attr("x", "-50%")
        .attr("y", "-50%")
        .attr("width", "200%")
        .attr("height", "200%");
      filter
        .append("feGaussianBlur")
        .attr("stdDeviation", "6")
        .attr("result", "coloredBlur");
      const merge = filter.append("feMerge");
      merge.append("feMergeNode").attr("in", "coloredBlur");
      merge.append("feMergeNode").attr("in", "SourceGraphic");
    });

    // Circle with gradient
    bubbleGroup
      .append("circle")
      .attr("r", (d) => d.r)
      .attr("fill", (d) => d.cluster.color)
      .attr("fill-opacity", 0.2)
      .attr("stroke", (d) => d.cluster.color)
      .attr("stroke-width", 2)
      .attr("stroke-opacity", 0.6)
      .attr("filter", (d) => `url(#glow-${d.cluster.id})`);

    // Inner filled circle
    bubbleGroup
      .append("circle")
      .attr("r", (d) => d.r * 0.85)
      .attr("fill", (d) => d.cluster.color)
      .attr("fill-opacity", 0.15);

    // Percentage label
    bubbleGroup
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dy", "-0.1em")
      .attr("fill", "white")
      .attr("font-size", (d) => `${Math.max(14, d.r * 0.4)}px`)
      .attr("font-weight", "700")
      .text((d) => `${d.cluster.sizePct}%`);

    // Name label
    bubbleGroup
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dy", (d) => `${Math.max(14, d.r * 0.22)}px`)
      .attr("fill", "rgba(255,255,255,0.7)")
      .attr("font-size", (d) => `${Math.max(9, d.r * 0.18)}px`)
      .attr("font-weight", "500")
      .text((d) => d.cluster.name);

    // Hover effects
    bubbleGroup
      .on("mouseenter", function (_, d) {
        d3.select(this)
          .select("circle")
          .transition()
          .duration(200)
          .attr("stroke-width", 3)
          .attr("stroke-opacity", 1);
        d3.select(this)
          .transition()
          .duration(200)
          .attr(
            "transform",
            `translate(${d.x},${d.y}) scale(1.06)`
          );
      })
      .on("mouseleave", function (_, d) {
        d3.select(this)
          .select("circle")
          .transition()
          .duration(200)
          .attr("stroke-width", 2)
          .attr("stroke-opacity", 0.6);
        d3.select(this)
          .transition()
          .duration(200)
          .attr(
            "transform",
            `translate(${d.x},${d.y}) scale(1)`
          );
      });
  }, [width, height, clusters, selected, onSelect]);

  return <svg ref={svgRef} className="overflow-visible" />;
}
