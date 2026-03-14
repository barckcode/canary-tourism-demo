import { useState, useCallback, useMemo } from "react";
import { motion } from "framer-motion";
import Panel from "../components/layout/Panel";
import AnimatedNumber from "../components/shared/AnimatedNumber";
import ErrorBoundary from "../components/shared/ErrorBoundary";
import ExportCSVButton from "../components/shared/ExportCSVButton";
import SparklineChart from "../components/shared/SparklineChart";
import TimeSlider from "../components/timeline/TimeSlider";
import TenerifeMap from "../components/map/TenerifeMap";
import { useDashboardKPIs, useDashboardSummary, useTopMarkets, useSeasonalPosition } from "../api/hooks";

const kpiConfig = [
  {
    key: "latest_arrivals" as const,
    label: "Arrivals",
    format: (n: number) => `${(n / 1000).toFixed(0)}K`,
    color: "text-ocean-400",
  },
  {
    key: "yoy_change" as const,
    label: "YoY Change",
    format: (n: number) => `${n > 0 ? "+" : ""}${n.toFixed(1)}%`,
    color: "text-tropical-400",
  },
  {
    key: "occupancy_rate" as const,
    label: "Occupancy",
    format: (n: number) => `${n.toFixed(1)}%`,
    color: "text-volcanic-400",
  },
  {
    key: "adr" as const,
    label: "ADR",
    format: (n: number) => `\u20AC${n.toFixed(0)}`,
    color: "text-ocean-300",
  },
  {
    key: "revpar" as const,
    label: "RevPAR",
    format: (n: number) =>
      n >= 1_000_000
        ? `\u20AC${(n / 1_000_000).toFixed(1)}M`
        : n >= 1_000
          ? `\u20AC${(n / 1_000).toFixed(0)}K`
          : `\u20AC${n.toFixed(0)}`,
    color: "text-purple-400",
  },
  {
    key: "avg_stay" as const,
    label: "Avg Stay",
    format: (n: number) => `${n.toFixed(1)}n`,
    color: "text-tropical-300",
  },
];

const stagger = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

export default function DashboardPage() {
  const { data: kpis, loading } = useDashboardKPIs();
  const { data: summary } = useDashboardSummary();
  const { data: topMarkets, loading: marketsLoading } = useTopMarkets();
  const { data: seasonal, loading: seasonalLoading } = useSeasonalPosition();
  const [selectedPeriod, setSelectedPeriod] = useState("2026-01");
  const handlePeriodChange = useCallback((period: string) => {
    setSelectedPeriod(period);
  }, []);

  const csvRows = useMemo<(string | number)[][]>(() => {
    if (!kpis) return [];
    return kpiConfig.map(({ key, label }) => [label, kpis[key]]);
  }, [kpis]);

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-6">
      {/* Header */}
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold gradient-text">Dashboard</h2>
          <p className="text-sm text-gray-500 mt-1">
            Tenerife tourism overview
          </p>
        </div>
        <div className="flex items-center gap-3">
          {kpis?.last_updated && (
            <span className="text-xs text-gray-600">
              Updated: {kpis.last_updated}
            </span>
          )}
          <ExportCSVButton
            headers={["KPI", "Value"]}
            rows={csvRows}
            filename={`dashboard-kpis-${selectedPeriod}`}
            metadata={{
              source: "Tenerife Tourism Intelligence - Dashboard",
              filters: { period: selectedPeriod },
            }}
            disabled={!kpis}
            ariaLabel="Export dashboard KPIs as CSV"
          />
        </div>
      </motion.div>

      {/* KPI cards */}
      <motion.div
        variants={fadeUp}
        className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4"
      >
        {kpiConfig.map(({ key, label, format, color }) => (
          <Panel key={key}>
            <div className="text-center">
              <div className={`kpi-value ${color}`}>
                {loading ? (
                  <div className="h-9 w-20 mx-auto bg-gray-800 rounded animate-pulse" />
                ) : kpis ? (
                  <AnimatedNumber value={kpis[key]} format={format} />
                ) : (
                  "\u2014"
                )}
              </div>
              <div className="kpi-label">{label}</div>
            </div>
          </Panel>
        ))}
      </motion.div>

      {/* Map + side panels */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <motion.div variants={fadeUp} className="lg:col-span-2">
          <Panel
            title="Tourism Map"
            subtitle="Municipality heatmap (3D)"
            className="h-[420px]"
            noPadding
          >
            <div className="h-[360px] rounded-b-2xl overflow-hidden">
              <ErrorBoundary>
                <TenerifeMap period={selectedPeriod} />
              </ErrorBoundary>
            </div>
          </Panel>
        </motion.div>

        <motion.div variants={fadeUp} className="space-y-4">
          <Panel title="Arrivals Trend" subtitle="Last 24 months">
            {summary?.arrivals_trend_24m ? (
              <SparklineChart
                data={summary.arrivals_trend_24m}
                forecast={summary.forecast}
                height={140}
              />
            ) : (
              <div className="h-[140px] flex items-center justify-center">
                <div className="h-[100px] w-full bg-gray-800/50 rounded animate-pulse" />
              </div>
            )}
          </Panel>

          <Panel title="Top Markets">
            <div className="space-y-3">
              {marketsLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="h-5 bg-gray-800 rounded animate-pulse" />
                  ))}
                </div>
              ) : topMarkets?.markets ? (
                topMarkets.markets.map(({ country, pct }) => (
                  <div key={country} className="flex items-center justify-between">
                    <span className="text-sm text-gray-300">{country}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${pct}%` }}
                          transition={{ duration: 0.8, delay: 0.3 }}
                          className="h-full bg-ocean-500 rounded-full"
                        />
                      </div>
                      <span className="text-xs text-gray-500 w-8 text-right">
                        {pct}%
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <span className="text-sm text-gray-500">No market data available</span>
              )}
            </div>
          </Panel>

          <Panel title="Seasonal Position">
            {seasonalLoading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-5 bg-gray-800 rounded animate-pulse" />
                ))}
              </div>
            ) : seasonal ? (
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">Peak Month</span>
                  <span className="text-volcanic-400 font-medium">{seasonal.peak_month}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">Current</span>
                  <span className={`font-medium ${
                    seasonal.current_position === "High" ? "text-tropical-400" :
                    seasonal.current_position === "Low" ? "text-red-400" :
                    "text-ocean-400"
                  }`}>{seasonal.current_position}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">Next 3 months</span>
                  <span className={`font-medium ${
                    seasonal.next_3_months === "High" ? "text-tropical-400" :
                    seasonal.next_3_months === "Low" ? "text-red-400" :
                    "text-ocean-400"
                  }`}>{seasonal.next_3_months}</span>
                </div>
              </div>
            ) : (
              <span className="text-sm text-gray-500">No seasonal data available</span>
            )}
          </Panel>
        </motion.div>
      </div>

      {/* Time Slider */}
      <motion.div variants={fadeUp}>
        <TimeSlider startYear={2010} endYear={2026} onChange={handlePeriodChange} />
      </motion.div>
    </motion.div>
  );
}
