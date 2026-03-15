import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { stagger, fadeUp } from "../utils/animations";
import Panel from "../components/layout/Panel";
import ChartContainer from "../components/shared/ChartContainer";
import ExportCSVButton from "../components/shared/ExportCSVButton";
import SankeyFlow from "../components/profiles/SankeyFlow";
import ClusterViz, {
  type ClusterData,
} from "../components/profiles/ClusterViz";
import ErrorBoundary from "../components/shared/ErrorBoundary";
import ErrorState from "../components/shared/ErrorState";
import { useProfiles, useProfileDetail, useNationalityProfiles, useFlowData, useSpendingByCluster } from "../api/hooks";

const CLUSTER_COLORS = ["#0087b9", "#f69b1a", "#28c066", "#a855f7"];

export default function ProfilesPage() {
  const { t } = useTranslation();
  const [selectedCluster, setSelectedCluster] = useState<ClusterData | null>(
    null
  );
  const { data: profilesData, error: profilesError, refetch: refetchProfiles } = useProfiles();
  const { data: detailData } = useProfileDetail(selectedCluster?.id ?? null);
  const { data: nationalityData, error: nationalityError, refetch: refetchNationality } = useNationalityProfiles();
  const { data: flowData, error: flowError, refetch: refetchFlow } = useFlowData();
  const { data: spendingData } = useSpendingByCluster();

  // Top 8 nationalities sorted by count
  const topNationalities = useMemo(() => {
    if (!nationalityData) return [];
    return [...nationalityData]
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [nationalityData]);

  const maxNatCount = useMemo(
    () => (topNationalities.length > 0 ? topNationalities[0].count : 1),
    [topNationalities]
  );

  const maxNights = useMemo(
    () =>
      topNationalities.length > 0
        ? Math.max(...topNationalities.map((n) => n.avg_nights))
        : 1,
    [topNationalities]
  );

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

  const profilesCsvRows = useMemo<(string | number)[][]>(() => {
    if (!profilesData?.clusters) return [];
    return profilesData.clusters.map((c) => [
      c.id,
      c.name,
      c.size_pct,
      Math.round(c.avg_age),
      Math.round(c.avg_spend),
      c.avg_nights.toFixed(1),
      c.top_nationalities?.map((n) => n.nationality).join("; ") || "",
      c.top_accommodations?.map((a) => a.type).join("; ") || "",
    ]);
  }, [profilesData]);

  const activeId = selectedCluster?.id ?? 0;

  // Build details from the selected cluster's profile data (list endpoint has all fields now)
  const activeCluster = profilesData?.clusters?.find((c) => c.id === activeId);
  const details = detailData
    ? [
        { label: t('profiles.profile'), value: detailData.name },
        { label: t('profiles.avgAge'), value: String(Math.round(detailData.avg_age)) },
        { label: t('profiles.avgSpend'), value: `\u20AC${Math.round(detailData.avg_spend).toLocaleString()}` },
        { label: t('profiles.avgStay'), value: `${detailData.avg_nights.toFixed(1)} ${t('profiles.nights')}` },
        { label: t('profiles.satisfaction'), value: detailData.avg_satisfaction != null ? `${detailData.avg_satisfaction.toFixed(1)}/10` : "\u2014" },
        { label: t('profiles.topMarket'), value: detailData.top_nationalities?.[0]?.nationality || "\u2014" },
      ]
    : activeCluster
      ? [
          { label: t('profiles.profile'), value: activeCluster.name },
          { label: t('profiles.avgAge'), value: String(Math.round(activeCluster.avg_age)) },
          { label: t('profiles.avgSpend'), value: `\u20AC${Math.round(activeCluster.avg_spend).toLocaleString()}` },
          { label: t('profiles.avgStay'), value: `${activeCluster.avg_nights.toFixed(1)} ${t('profiles.nights')}` },
          { label: t('profiles.satisfaction'), value: activeCluster.avg_satisfaction != null ? `${activeCluster.avg_satisfaction.toFixed(1)}/10` : "\u2014" },
          { label: t('profiles.topMarket'), value: activeCluster.top_nationalities?.[0]?.nationality || "\u2014" },
        ]
      : [
          { label: t('profiles.profile'), value: "\u2014" },
          { label: t('profiles.avgAge'), value: "\u2014" },
          { label: t('profiles.avgSpend'), value: "\u2014" },
          { label: t('profiles.avgStay'), value: "\u2014" },
          { label: t('profiles.satisfaction'), value: "\u2014" },
          { label: t('profiles.topMarket'), value: "\u2014" },
        ];

  // Get spending from the dedicated spending endpoint (real microdata)
  const spending = spendingData?.spending_by_cluster?.[String(activeId)] ?? [];

  // Activities and motivations from the selected cluster
  const activities = detailData?.top_activities ?? activeCluster?.top_activities ?? [];
  const motivations = detailData?.top_motivations ?? activeCluster?.top_motivations ?? [];

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold gradient-text">{t('profiles.title')}</h1>
          <p className="text-sm text-gray-400 mt-1">
            {t('profiles.subtitle')}
          </p>
        </div>
        <ExportCSVButton
          headers={["Cluster ID", "Name", "Size %", "Avg Age", "Avg Spend", "Avg Nights", "Top Nationalities", "Top Accommodations"]}
          rows={profilesCsvRows}
          filename="tourist-profiles"
          metadata={{
            source: "Tenerife Tourism Intelligence - Tourist Profiles",
          }}
          disabled={profilesCsvRows.length === 0}
          ariaLabel={t('profiles.exportAriaLabel')}
        />
      </motion.div>

      {/* D3 Force Bubble Chart */}
      <motion.div variants={fadeUp}>
        <Panel
          title={t('profiles.segmentBubbles')}
          subtitle={t('profiles.segmentBubblesSubtitle')}
        >
          {profilesError ? (
            <ErrorState message={t('profiles.couldNotLoadProfiles')} onRetry={refetchProfiles} />
          ) : (
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
          )}
        </Panel>
      </motion.div>

      {/* Detail + Spending -- updates based on selected cluster */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <motion.div variants={fadeUp}>
          <Panel
            title={t('profiles.selectedSegment')}
            subtitle={selectedCluster?.description || t('profiles.clickBubble')}
          >
            <div className="space-y-3 py-2">
              {details.map(({ label, value }) => (
                <div
                  key={label}
                  className="flex justify-between items-center py-1.5 border-b border-gray-800/30 last:border-0"
                >
                  <span className="text-sm text-gray-400">{label}</span>
                  <span className="text-sm text-gray-200 font-medium">
                    {value}
                  </span>
                </div>
              ))}
            </div>
          </Panel>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Panel title={t('profiles.spendingBreakdown')} subtitle={t('profiles.spendingSubtitle')}>
            <div className="space-y-4 py-2">
              {spending.length > 0 ? (
                spending.map(({ category, amount, pct }) => (
                  <div key={category}>
                    <div className="flex justify-between text-sm mb-1.5">
                      <span className="text-gray-400">{category}</span>
                      <span className="text-gray-300">{"\u20AC"}{Math.round(amount)}</span>
                    </div>
                    <div
                      className="w-full h-2 bg-gray-800 rounded-full overflow-hidden"
                      role="progressbar"
                      aria-valuenow={pct}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label={t('profiles.spendingAriaLabel', { category, amount: Math.round(amount), pct })}
                    >
                      <motion.div
                        key={`${activeId}-${category}`}
                        initial={{ width: 0 }}
                        animate={{ width: `${pct}%` }}
                        transition={{ duration: 0.6, delay: 0.1 }}
                        className="h-full bg-gradient-to-r from-ocean-500 to-tropical-500 rounded-full"
                      />
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-gray-400 py-4 text-center">{t('profiles.noSpendingData')}</p>
              )}
            </div>
          </Panel>
        </motion.div>
      </div>

      {/* Activities + Motivations -- per selected cluster */}
      {(activities.length > 0 || motivations.length > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {activities.length > 0 && (
            <motion.div variants={fadeUp}>
              <Panel title={t('profiles.topActivities')} subtitle={t('profiles.topActivitiesSubtitle')}>
                <div className="flex flex-wrap gap-2 py-3">
                  {activities.map((activity) => (
                    <span
                      key={activity}
                      className="px-3 py-1.5 text-sm bg-ocean-500/10 text-ocean-400 border border-ocean-500/20 rounded-full"
                    >
                      {activity}
                    </span>
                  ))}
                </div>
              </Panel>
            </motion.div>
          )}

          {motivations.length > 0 && (
            <motion.div variants={fadeUp}>
              <Panel title={t('profiles.topMotivations')} subtitle={t('profiles.topMotivationsSubtitle')}>
                <div className="flex flex-wrap gap-2 py-3">
                  {motivations.map((motivation) => (
                    <span
                      key={motivation}
                      className="px-3 py-1.5 text-sm bg-tropical-500/10 text-tropical-400 border border-tropical-500/20 rounded-full"
                    >
                      {motivation}
                    </span>
                  ))}
                </div>
              </Panel>
            </motion.div>
          )}
        </div>
      )}

      {/* Nationality Profiles */}
      {nationalityError && (
        <motion.div variants={fadeUp}>
          <ErrorState message={t('profiles.couldNotLoadNationalities')} onRetry={refetchNationality} />
        </motion.div>
      )}
      {!nationalityError && topNationalities.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <motion.div variants={fadeUp}>
            <Panel title={t('profiles.topNationalities')} subtitle={t('profiles.topNationalitiesSubtitle')}>
              <div className="space-y-4 py-2">
                {topNationalities.map(({ nationality, count, avg_spend }) => (
                  <div key={nationality}>
                    <div className="flex justify-between text-sm mb-1.5">
                      <span className="text-gray-300">{nationality}</span>
                      <span className="text-gray-400">
                        {count.toLocaleString()} {t('profiles.visitors')} {"\u00B7"} {"\u20AC"}{Math.round(avg_spend)}
                      </span>
                    </div>
                    <div
                      className="w-full h-2 bg-gray-800 rounded-full overflow-hidden"
                      role="progressbar"
                      aria-valuenow={Math.round((count / maxNatCount) * 100)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label={`${nationality} ${t('profiles.visitors')} ${count.toLocaleString()}`}
                    >
                      <motion.div
                        key={`nat-${nationality}`}
                        initial={{ width: 0 }}
                        animate={{ width: `${(count / maxNatCount) * 100}%` }}
                        transition={{ duration: 0.6, delay: 0.1 }}
                        className="h-full bg-gradient-to-r from-ocean-500 to-tropical-500 rounded-full"
                      />
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          </motion.div>

          <motion.div variants={fadeUp}>
            <Panel title={t('profiles.avgStayByMarket')} subtitle={t('profiles.avgStayByMarketSubtitle')}>
              <div className="space-y-4 py-2">
                {topNationalities.map(({ nationality, avg_nights }) => (
                  <div key={nationality}>
                    <div className="flex justify-between text-sm mb-1.5">
                      <span className="text-gray-300">{nationality}</span>
                      <span className="text-gray-400">
                        {avg_nights.toFixed(1)} {t('profiles.nights')}
                      </span>
                    </div>
                    <div
                      className="w-full h-2 bg-gray-800 rounded-full overflow-hidden"
                      role="progressbar"
                      aria-valuenow={Math.round((avg_nights / maxNights) * 100)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label={`${nationality} ${t('profiles.avgStay')} ${avg_nights.toFixed(1)} ${t('profiles.nights')}`}
                    >
                      <motion.div
                        key={`stay-${nationality}`}
                        initial={{ width: 0 }}
                        animate={{ width: `${(avg_nights / maxNights) * 100}%` }}
                        transition={{ duration: 0.6, delay: 0.1 }}
                        className="h-full bg-gradient-to-r from-volcanic-500 to-tropical-500 rounded-full"
                      />
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          </motion.div>
        </div>
      )}

      {/* Sankey */}
      <motion.div variants={fadeUp}>
        <Panel
          title={t('profiles.touristFlow')}
          subtitle={t('profiles.touristFlowSubtitle')}
        >
          {flowError ? (
            <ErrorState message={t('profiles.couldNotLoadFlow')} onRetry={refetchFlow} />
          ) : (
            <ErrorBoundary>
              <ChartContainer height={420}>
                {({ width, height }) => (
                  <SankeyFlow width={width} height={height} data={flowData} />
                )}
              </ChartContainer>
            </ErrorBoundary>
          )}
        </Panel>
      </motion.div>
    </motion.div>
  );
}
