import { useEffect, useRef } from "react";
import * as d3 from "d3";
import {
  sankey as d3Sankey,
  sankeyLinkHorizontal,
  SankeyNode,
  SankeyLink,
} from "d3-sankey";

interface SankeyFlowProps {
  width: number;
  height: number;
}

interface NodeData {
  id: number;
  name: string;
  category: string;
}

interface LinkData {
  source: number;
  target: number;
  value: number;
}

// Mock data: Country → Zone → Accommodation
function getMockSankeyData(): { nodes: NodeData[]; links: LinkData[] } {
  return {
    nodes: [
      // Countries (0-4)
      { id: 0, name: "United Kingdom", category: "country" },
      { id: 1, name: "Germany", category: "country" },
      { id: 2, name: "Sweden", category: "country" },
      { id: 3, name: "Spain", category: "country" },
      { id: 4, name: "France", category: "country" },
      // Zones (5-8)
      { id: 5, name: "Adeje", category: "zone" },
      { id: 6, name: "Arona", category: "zone" },
      { id: 7, name: "Puerto de la Cruz", category: "zone" },
      { id: 8, name: "Santa Cruz", category: "zone" },
      // Accommodation (9-12)
      { id: 9, name: "4-5\u2605 Hotel", category: "accommodation" },
      { id: 10, name: "3\u2605 Hotel", category: "accommodation" },
      { id: 11, name: "Apartment", category: "accommodation" },
      { id: 12, name: "Villa/Rural", category: "accommodation" },
    ],
    links: [
      // UK → zones
      { source: 0, target: 5, value: 45 },
      { source: 0, target: 6, value: 35 },
      { source: 0, target: 7, value: 12 },
      { source: 0, target: 8, value: 8 },
      // Germany → zones
      { source: 1, target: 5, value: 30 },
      { source: 1, target: 6, value: 25 },
      { source: 1, target: 7, value: 28 },
      { source: 1, target: 8, value: 7 },
      // Sweden → zones
      { source: 2, target: 5, value: 18 },
      { source: 2, target: 6, value: 20 },
      { source: 2, target: 7, value: 5 },
      // Spain → zones
      { source: 3, target: 7, value: 15 },
      { source: 3, target: 8, value: 25 },
      { source: 3, target: 5, value: 8 },
      // France → zones
      { source: 4, target: 5, value: 10 },
      { source: 4, target: 6, value: 8 },
      { source: 4, target: 7, value: 7 },
      // Zones → accommodation
      { source: 5, target: 9, value: 55 },
      { source: 5, target: 10, value: 25 },
      { source: 5, target: 11, value: 20 },
      { source: 5, target: 12, value: 11 },
      { source: 6, target: 9, value: 40 },
      { source: 6, target: 10, value: 20 },
      { source: 6, target: 11, value: 25 },
      { source: 6, target: 12, value: 3 },
      { source: 7, target: 10, value: 30 },
      { source: 7, target: 11, value: 22 },
      { source: 7, target: 9, value: 10 },
      { source: 7, target: 12, value: 5 },
      { source: 8, target: 10, value: 15 },
      { source: 8, target: 11, value: 18 },
      { source: 8, target: 9, value: 5 },
      { source: 8, target: 12, value: 2 },
    ],
  };
}

const categoryColors: Record<string, string> = {
  country: "#0087b9",
  zone: "#f69b1a",
  accommodation: "#28c066",
};

const MARGIN = { top: 10, right: 10, bottom: 10, left: 10 };

export default function SankeyFlow({ width, height }: SankeyFlowProps) {
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

    const data = getMockSankeyData();

    const sankeyGenerator = d3Sankey<NodeData, LinkData>()
      .nodeId((d: SankeyNode<NodeData, LinkData>) => d.id)
      .nodeWidth(14)
      .nodePadding(12)
      .extent([
        [0, 0],
        [w, h],
      ]);

    const { nodes, links } = sankeyGenerator({
      nodes: data.nodes.map((d) => ({ ...d })),
      links: data.links.map((d) => ({ ...d })),
    });

    // Links
    const linkGroup = g.append("g").attr("fill", "none");

    linkGroup
      .selectAll("path")
      .data(links)
      .join("path")
      .attr("d", sankeyLinkHorizontal())
      .attr("stroke-width", (d) => Math.max(1, (d as SankeyLink<NodeData, LinkData>).width || 1))
      .attr("stroke", (d) => {
        const sourceNode = d.source as SankeyNode<NodeData, LinkData>;
        const color = categoryColors[sourceNode.category] || "#555";
        return color;
      })
      .attr("stroke-opacity", 0.25)
      .on("mouseenter", function () {
        d3.select(this).attr("stroke-opacity", 0.5);
      })
      .on("mouseleave", function () {
        d3.select(this).attr("stroke-opacity", 0.25);
      });

    // Nodes
    const nodeGroup = g.append("g");

    nodeGroup
      .selectAll("rect")
      .data(nodes)
      .join("rect")
      .attr("x", (d) => d.x0 || 0)
      .attr("y", (d) => d.y0 || 0)
      .attr("width", (d) => (d.x1 || 0) - (d.x0 || 0))
      .attr("height", (d) => Math.max(1, (d.y1 || 0) - (d.y0 || 0)))
      .attr("fill", (d) => categoryColors[d.category] || "#555")
      .attr("rx", 2)
      .attr("opacity", 0.85);

    // Labels
    nodeGroup
      .selectAll("text")
      .data(nodes)
      .join("text")
      .attr("x", (d) => {
        const x0 = d.x0 || 0;
        const x1 = d.x1 || 0;
        return x0 < w / 3 ? x1 + 6 : x0 - 6;
      })
      .attr("y", (d) => ((d.y0 || 0) + (d.y1 || 0)) / 2)
      .attr("dy", "0.35em")
      .attr("text-anchor", (d) => ((d.x0 || 0) < w / 3 ? "start" : "end"))
      .attr("fill", "rgba(255,255,255,0.6)")
      .attr("font-size", "11px")
      .text((d) => d.name);

    // Category labels (top)
    const categories = [
      { label: "Country", x: 0 },
      { label: "Zone", x: w / 2 },
      { label: "Accommodation", x: w },
    ];
    g.append("g")
      .selectAll("text")
      .data(categories)
      .join("text")
      .attr("x", (d) => d.x)
      .attr("y", -2)
      .attr("text-anchor", (_d, i) => (i === 0 ? "start" : i === 1 ? "middle" : "end"))
      .attr("fill", "rgba(255,255,255,0.3)")
      .attr("font-size", "10px")
      .attr("text-transform", "uppercase")
      .text((d) => d.label);
  }, [width, height]);

  return <svg ref={svgRef} className="overflow-visible" />;
}
