import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import Panel from "../components/layout/Panel";
import ChartContainer from "../components/shared/ChartContainer";
import SankeyFlow from "../components/profiles/SankeyFlow";
import ClusterViz, {
  type ClusterData,
} from "../components/profiles/ClusterViz";
import ErrorBoundary from "../components/shared/ErrorBoundary";
import { useProfiles, useProfileDetail } from "../api/hooks";

const stagger = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

const segmentDetails: Record<
  number,
  { label: string; value: string }[]
> = {
  0: [
    { label: "Profile", value: "Budget Young" },
    { label: "Age Range", value: "18-32" },
    { label: "Avg Spend", value: "\u20AC350" },
    { label: "Avg Stay", value: "5 nights" },
    { label: "Accommodation", value: "Apartment" },
    { label: "Purpose", value: "Leisure / Nightlife" },
  ],
  1: [
    { label: "Profile", value: "High Spender" },
    { label: "Age Range", value: "45-60" },
    { label: "Avg Spend", value: "\u20AC1,200" },
    { label: "Avg Stay", value: "8 nights" },
    { label: "Accommodation", value: "4-star Hotel" },
    { label: "Purpose", value: "Family Vacation" },
  ],
  2: [
    { label: "Profile", value: "Budget Older" },
    { label: "Age Range", value: "60-75" },
    { label: "Avg Spend", value: "\u20AC400" },
    { label: "Avg Stay", value: "7 nights" },
    { label: "Accommodation", value: "3-star Hotel" },
    { label: "Purpose", value: "Relaxation" },
  ],
  3: [
    { label: "Profile", value: "Premium VIP" },
    { label: "Age Range", value: "35-55" },
    { label: "Avg Spend", value: "\u20AC2,500" },
    { label: "Avg Stay", value: "14 nights" },
    { label: "Accommodation", value: "Villa / 5-star" },
    { label: "Purpose", value: "Luxury Retreat" },
  ],
};

const spendingByCluster: Record<
  number,
  { category: string; amount: number; pct: number }[]
> = {
  0: [
    { category: "Accommodation", amount: 100, pct: 29 },
    { category: "Restaurants", amount: 80, pct: 23 },
    { category: "Nightlife", amount: 70, pct: 20 },
    { category: "Shopping", amount: 50, pct: 14 },
    { category: "Transport", amount: 30, pct: 9 },
    { category: "Other", amount: 20, pct: 6 },
  ],
  1: [
    { category: "Accommodation", amount: 420, pct: 35 },
    { category: "Restaurants", amount: 280, pct: 23 },
    { category: "Excursions", amount: 180, pct: 15 },
    { category: "Shopping", amount: 120, pct: 10 },
    { category: "Transport", amount: 90, pct: 8 },
    { category: "Other", amount: 60, pct: 5 },
  ],
  2: [
    { category: "Accommodation", amount: 140, pct: 35 },
    { category: "Restaurants", amount: 90, pct: 23 },
    { category: "Excursions", amount: 60, pct: 15 },
    { category: "Shopping", amount: 50, pct: 13 },
    { category: "Health/Spa", amount: 35, pct: 9 },
    { category: "Other", amount: 25, pct: 6 },
  ],
  3: [
    { category: "Accommodation", amount: 900, pct: 36 },
    { category: "Restaurants", amount: 500, pct: 20 },
    { category: "Excursions", amount: 400, pct: 16 },
    { category: "Sports/Golf", amount: 300, pct: 12 },
    { category: "Shopping", amount: 250, pct: 10 },
    { category: "Other", amount: 150, pct: 6 },
  ],
};

const CLUSTER_COLORS = ["#0087b9", "#f69b1a", "#28c066", "#a855f7"];

export default function ProfilesPage() {
  const [selectedCluster, setSelectedCluster] = useState<ClusterData | null>(
    null
  );
  const { data: profilesData } = useProfiles();
  const { data: detailData } = useProfileDetail(selectedCluster?.id ?? null);

  // Map API clusters to ClusterViz format (with fallback)
  const apiClusters = useMemo<ClusterData[] | undefined>(() => {
    if (!profilesData?.clusters) return undefined;
    return profilesData.clusters.map((c, i) => ({
      id: c.id,
      name: c.name,
      sizePct: c.size_pct,
      avgAge: c.avg_age,
      avgSpend: c.avg_spend,
      avgNights: c.avg_nights,
      color: CLUSTER_COLORS[i % CLUSTER_COLORS.length],
      description: `${c.top_nationalities?.[0]?.nationality || "Various"} tourists, avg \u20AC${c.avg_spend}`,
    }));
  }, [profilesData]);

  const activeId = selectedCluster?.id ?? 1;
  const details = detailData
    ? [
        { label: "Profile", value: detailData.name },
        { label: "Avg Age", value: String(Math.round(detailData.avg_age)) },
        { label: "Avg Spend", value: `\u20AC${Math.round(detailData.avg_spend).toLocaleString()}` },
        { label: "Avg Stay", value: `${detailData.avg_nights.toFixed(1)} nights` },
        { label: "Top Market", value: detailData.top_nationalities?.[0]?.nationality || "—" },
        { label: "Top Accom.", value: detailData.top_accommodations?.[0]?.type || "—" },
      ]
    : segmentDetails[activeId];
  const spending = spendingByCluster[activeId];

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      <motion.div variants={fadeUp}>
        <h2 className="text-2xl font-bold gradient-text">Tourist Profiles</h2>
        <p className="text-sm text-gray-500 mt-1">
          Behavioral segmentation from survey microdata
        </p>
      </motion.div>

      {/* D3 Force Bubble Chart */}
      <motion.div variants={fadeUp}>
        <Panel
          title="Segment Bubbles"
          subtitle="Click a segment to explore its profile"
        >
          <ErrorBoundary>
            <ChartContainer height={320}>
              {({ width, height }) => (
                <ClusterViz
                  width={width}
                  height={height}
                  clusters={apiClusters}
                  onSelect={setSelectedCluster}
                />
              )}
            </ChartContainer>
          </ErrorBoundary>
        </Panel>
      </motion.div>

      {/* Detail + Spending — updates based on selected cluster */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <motion.div variants={fadeUp}>
          <Panel
            title="Selected Segment"
            subtitle={selectedCluster?.description || "Click a bubble above"}
          >
            <div className="space-y-3 py-2">
              {details.map(({ label, value }) => (
                <div
                  key={label}
                  className="flex justify-between items-center py-1.5 border-b border-gray-800/30 last:border-0"
                >
                  <span className="text-sm text-gray-500">{label}</span>
                  <span className="text-sm text-gray-200 font-medium">
                    {value}
                  </span>
                </div>
              ))}
            </div>
          </Panel>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Panel title="Spending Breakdown" subtitle="Where the money goes">
            <div className="space-y-4 py-2">
              {spending.map(({ category, amount, pct }) => (
                <div key={category}>
                  <div className="flex justify-between text-sm mb-1.5">
                    <span className="text-gray-400">{category}</span>
                    <span className="text-gray-300">{"\u20AC"}{amount}</span>
                  </div>
                  <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden">
                    <motion.div
                      key={`${activeId}-${category}`}
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={{ duration: 0.6, delay: 0.1 }}
                      className="h-full bg-gradient-to-r from-ocean-500 to-tropical-500 rounded-full"
                    />
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </motion.div>
      </div>

      {/* Sankey */}
      <motion.div variants={fadeUp}>
        <Panel
          title="Tourist Flow"
          subtitle="Country \u2192 Zone \u2192 Accommodation"
        >
          <ErrorBoundary>
            <ChartContainer height={300}>
              {({ width, height }) => (
                <SankeyFlow width={width} height={height} />
              )}
            </ChartContainer>
          </ErrorBoundary>
        </Panel>
      </motion.div>
    </motion.div>
  );
}
