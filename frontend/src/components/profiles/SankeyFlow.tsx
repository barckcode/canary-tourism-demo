import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
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
  loading?: boolean;
  data?: {
    nodes: { id: string; label: string }[];
    links: { source: string; target: string; value: number }[];
  } | null;
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

const categoryColors: Record<string, string> = {
  country: "#0087b9",
  zone: "#f69b1a",
  accommodation: "#28c066",
};

const MARGIN = { top: 10, right: 10, bottom: 10, left: 10 };

// Convert API data (string IDs) to internal format (numeric IDs)
function convertApiData(apiData: {
  nodes: { id: string; label: string }[];
  links: { source: string; target: string; value: number }[];
}): { nodes: NodeData[]; links: LinkData[] } {
  const idMap = new Map<string, number>();
  const nodes: NodeData[] = apiData.nodes.map((n, i) => {
    idMap.set(n.id, i);
    // Determine category from ID prefix
    let category = "country";
    if (n.id.startsWith("accom_")) category = "accommodation";
    else if (n.id.startsWith("zone_")) category = "zone";
    return { id: i, name: n.label, category };
  });
  const links: LinkData[] = apiData.links
    .filter((l) => idMap.has(l.source) && idMap.has(l.target))
    .map((l) => ({
      source: idMap.get(l.source)!,
      target: idMap.get(l.target)!,
      value: l.value,
    }));
  return { nodes, links };
}

export default function SankeyFlow({ width, height, loading = false, data: apiData }: SankeyFlowProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const { t } = useTranslation();

  const hasData = apiData != null && apiData.nodes.length > 0;

  useEffect(() => {
    if (!svgRef.current || width <= 0 || height <= 0 || !hasData) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();
    svg.append("title").text(t('accessibility.sankeyFlow'));

    const w = width - MARGIN.left - MARGIN.right;
    const h = height - MARGIN.top - MARGIN.bottom;

    const g = svg
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${MARGIN.left},${MARGIN.top})`);

    const data = convertApiData(apiData!);

    // Filter out orphan nodes -- keep only nodes referenced in at least one link
    const connectedNodeIds = new Set<number>();
    data.links.forEach(link => {
      connectedNodeIds.add(link.source);
      connectedNodeIds.add(link.target);
    });
    data.nodes = data.nodes.filter(node => connectedNodeIds.has(node.id));

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

    // Category labels (top) — dynamically derived from data
    const uniqueCategories = [...new Set(data.nodes.map((n) => n.category))];
    const N = uniqueCategories.length;
    const categoryLabels: { label: string; x: number; anchor: string }[] =
      N <= 1
        ? uniqueCategories.map((cat) => ({
            label: cat.charAt(0).toUpperCase() + cat.slice(1),
            x: w / 2,
            anchor: "middle",
          }))
        : uniqueCategories.map((cat, i) => ({
            label: cat.charAt(0).toUpperCase() + cat.slice(1),
            x: (i / (N - 1)) * w,
            anchor: i === 0 ? "start" : i === N - 1 ? "end" : "middle",
          }));
    g.append("g")
      .selectAll("text")
      .data(categoryLabels)
      .join("text")
      .attr("x", (d) => d.x)
      .attr("y", -2)
      .attr("text-anchor", (d) => d.anchor)
      .attr("fill", "rgba(255,255,255,0.3)")
      .attr("font-size", "10px")
      .attr("text-transform", "uppercase")
      .text((d) => d.label);

    return () => {
      if (svgRef.current) {
        d3.select(svgRef.current).selectAll("*").remove();
      }
    };
  }, [width, height, apiData, hasData, t]);

  if (loading) {
    return (
      <div
        className="animate-pulse space-y-4"
        style={{ width, height }}
        role="status"
        aria-live="polite"
        aria-label={t('common.loading')}
      >
        <div className="h-8 bg-white/10 rounded w-1/3"></div>
        <div className="h-64 bg-white/10 rounded"></div>
      </div>
    );
  }

  if (!hasData) {
    return (
      <div
        className="flex items-center justify-center text-gray-400"
        style={{ width, height }}
      >
        <p className="text-sm">{t('profiles.noFlowData')}</p>
      </div>
    );
  }

  return (
    <div>
      <svg ref={svgRef} className="overflow-visible" role="img" aria-label={t('accessibility.sankeyFlow')} />
    </div>
  );
}
