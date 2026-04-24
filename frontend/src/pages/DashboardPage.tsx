import { useState, useCallback, useMemo } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { formatCompactNumber } from "../utils/format";
import { stagger, fadeUp } from "../utils/animations";
import Panel from "../components/layout/Panel";
import AnimatedNumber from "../components/shared/AnimatedNumber";
import ErrorBoundary from "../components/shared/ErrorBoundary";
import ErrorState from "../components/shared/ErrorState";
import ExportCSVButton from "../components/shared/ExportCSVButton";
import SparklineChart from "../components/shared/SparklineChart";
import TimeSlider from "../components/timeline/TimeSlider";
import TenerifeMap from "../components/map/TenerifeMap";
import { useDashboardKPIs, useDashboardSummary, useTopMarkets, useSeasonalPosition, DashboardKPIs } from "../api/hooks";
import { usePageTitle } from "../hooks/usePageTitle";

interface KpiConfigItem {
  key: keyof DashboardKPIs;
  labelKey: string;
  format: (n: number) => string;
  color: string;
  yoyKey?: keyof DashboardKPIs;
}

function getDefaultPeriod(): string {
  const now = new Date();
  now.setMonth(now.getMonth() - 1);
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

const kpiConfig: KpiConfigItem[] = [
  {
    key: "latest_arrivals" as const,
    labelKey: "dashboard.arrivals",
    format: (n: number) => `${(n / 1000).toFixed(0)}K`,
    color: "text-ocean-400",
  },
  {
    key: "yoy_change" as const,
    labelKey: "dashboard.yoyChange",
    format: (n: number) => `${n > 0 ? "+" : ""}${n.toFixed(1)}%`,
    color: "text-tropical-400",
  },
  {
    key: "occupancy_rate" as const,
    labelKey: "dashboard.occupancy",
    format: (n: number) => `${n.toFixed(1)}%`,
    color: "text-volcanic-400",
  },
  {
    key: "adr" as const,
    labelKey: "dashboard.adr",
    format: (n: number) => `\u20AC${n.toFixed(0)}`,
    color: "text-ocean-300",
  },
  {
    key: "revpar" as const,
    labelKey: "dashboard.revpar",
    format: (n: number) => `\u20AC${formatCompactNumber(n)}`,
    color: "text-purple-400",
  },
  {
    key: "avg_stay" as const,
    labelKey: "dashboard.avgStay",
    format: (n: number) => `${n.toFixed(1)}n`,
    color: "text-tropical-300",
  },
  {
    key: "daily_spend" as const,
    labelKey: "dashboard.dailySpend",
    format: (n: number) => `${n.toFixed(0)} \u20AC`,
    color: "text-ocean-400",
  },
  {
    key: "avg_stay_ine" as const,
    labelKey: "dashboard.avgStayIne",
    format: (n: number) => `${n.toFixed(1)}d`,
    color: "text-volcanic-300",
  },
  {
    key: "employment_total" as const,
    labelKey: "dashboard.employmentTotal",
    format: (n: number) => `${n.toLocaleString("en", { maximumFractionDigits: 1 })}K`,
    color: "text-tropical-400",
    yoyKey: "employment_total_yoy" as const,
  },
  {
    key: "employment_services" as const,
    labelKey: "dashboard.employmentServices",
    format: (n: number) => `${n.toLocaleString("en", { maximumFractionDigits: 1 })}K`,
    color: "text-ocean-300",
    yoyKey: "employment_services_yoy" as const,
  },
  {
    key: "iph_index" as const,
    labelKey: "dashboard.iphIndex",
    format: (n: number) => n.toFixed(1),
    color: "text-volcanic-400",
    yoyKey: "iph_variation" as const,
  },
];

export default function DashboardPage() {
  const { t } = useTranslation();
  usePageTitle("nav.dashboard");
  const [selectedPeriod, setSelectedPeriod] = useState(getDefaultPeriod);
  const { data: kpis, loading, error: kpisError, refetch: refetchKpis } = useDashboardKPIs(selectedPeriod);
  const { data: summary, error: summaryError, refetch: refetchSummary } = useDashboardSummary();
  const { data: topMarkets, loading: marketsLoading, error: marketsError, refetch: refetchMarkets } = useTopMarkets();
  const { data: seasonal, loading: seasonalLoading, error: seasonalError, refetch: refetchSeasonal } = useSeasonalPosition();
  const handlePeriodChange = useCallback((period: string) => {
    setSelectedPeriod(period);
  }, []);


  const csvRows = useMemo<(string | number)[][]>(() => {
    if (!kpis) return [];
    return kpiConfig.map(({ key, labelKey }) => [t(labelKey), kpis[key] ?? "—"]);
  }, [kpis, t]);

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-6">
      {/* Header */}
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold gradient-text">{t('dashboard.title')}</h1>
          <p className="text-sm text-gray-400 mt-1">
            {t('dashboard.subtitle')}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {kpis?.latest_period && (
            <span className="text-xs text-gray-500">
              {t('dashboard.dataAsOf', { period: kpis.latest_period })}
            </span>
          )}
          {kpis?.last_updated && (
            <span className="text-xs text-gray-400">
              {t('common.updated')}: {kpis.last_updated}
            </span>
          )}
          <ExportCSVButton
            headers={[t('dashboard.kpi'), t('dashboard.value')]}
            rows={csvRows}
            filename={`dashboard-kpis-${selectedPeriod}`}
            metadata={{
              source: "Tenerife Tourism Intelligence - Dashboard",
              filters: { period: selectedPeriod },
            }}
            disabled={!kpis}
            ariaLabel={t('dashboard.exportAriaLabel')}
          />
        </div>
      </motion.div>

      {/* Viewing period indicator */}
      <motion.div variants={fadeUp} className="flex items-center gap-2">
        <span className="text-xs text-gray-500">
          {t('dashboard.viewingPeriod')}: {selectedPeriod || kpis?.latest_period || '\u2014'}
        </span>
      </motion.div>

      {/* KPI cards */}
      {kpisError ? (
        <motion.div variants={fadeUp}>
          <ErrorState message={t('dashboard.couldNotLoadKPI')} onRetry={refetchKpis} />
        </motion.div>
      ) : (
        <motion.div
          variants={fadeUp}
          className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4"
          aria-busy={loading}
        >
          {kpiConfig.map(({ key, labelKey, format, color, yoyKey }) => (
            <Panel key={key}>
              <div className="text-center">
                <div className={`kpi-value ${color}`}>
                  {loading ? (
                    <div className="h-9 w-20 mx-auto bg-gray-800 rounded animate-pulse" />
                  ) : kpis && kpis[key] != null ? (
                    <AnimatedNumber value={kpis[key] as number} format={format} />
                  ) : (
                    "\u2014"
                  )}
                </div>
                <div className="kpi-label">{t(labelKey)}</div>
                {yoyKey && kpis && kpis[yoyKey] != null && !loading && (
                  <div className={`text-xs mt-1 font-medium ${(kpis[yoyKey] as number) >= 0 ? "text-tropical-400" : "text-red-400"}`}>
                    {(kpis[yoyKey] as number) >= 0 ? "\u25B2" : "\u25BC"}{" "}
                    {(kpis[yoyKey] as number) > 0 ? "+" : ""}{(kpis[yoyKey] as number).toFixed(1)}% YoY
                  </div>
                )}
              </div>
            </Panel>
          ))}
        </motion.div>
      )}

      {/* Map + side panels */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <motion.div variants={fadeUp} className="lg:col-span-2">
          <Panel
            title={t('dashboard.tourismMap')}
            subtitle={t('dashboard.mapSubtitle')}
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
          <Panel title={t('dashboard.arrivalsTrend')} subtitle={t('dashboard.last24Months')}>
            <div aria-busy={!summary && !summaryError}>
            {summaryError ? (
              <ErrorState message={t('dashboard.couldNotLoadTrend')} onRetry={refetchSummary} />
            ) : summary?.arrivals_trend_24m ? (
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
            </div>
          </Panel>

          <Panel title={t('dashboard.topMarkets')}>
            <div className="space-y-3" aria-busy={marketsLoading}>
              {marketsError ? (
                <ErrorState message={t('dashboard.couldNotLoadMarkets')} onRetry={refetchMarkets} />
              ) : marketsLoading ? (
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
                      <div
                        className="w-24 h-1.5 bg-gray-800 rounded-full overflow-hidden"
                        role="progressbar"
                        aria-valuenow={pct}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label={t('dashboard.marketShareLabel', { country, pct })}
                      >
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${pct}%` }}
                          transition={{ duration: 0.8, delay: 0.3 }}
                          className="h-full bg-ocean-500 rounded-full"
                        />
                      </div>
                      <span className="text-xs text-gray-400 w-8 text-right">
                        {pct}%
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <span className="text-sm text-gray-400">{t('dashboard.noMarketData')}</span>
              )}
            </div>
          </Panel>

          <Panel title={t('dashboard.seasonalPosition')}>
            <div aria-busy={seasonalLoading}>
            {seasonalError ? (
              <ErrorState message={t('dashboard.couldNotLoadSeasonal')} onRetry={refetchSeasonal} />
            ) : seasonalLoading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-5 bg-gray-800 rounded animate-pulse" />
                ))}
              </div>
            ) : seasonal ? (
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">{t('dashboard.peakMonth')}</span>
                  <span className="text-volcanic-400 font-medium">{seasonal.peak_month}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">{t('dashboard.current')}</span>
                  <span className={`font-medium ${
                    seasonal.current_position === "High" ? "text-tropical-400" :
                    seasonal.current_position === "Low" ? "text-red-400" :
                    "text-ocean-400"
                  }`}>{seasonal.current_position}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">{t('dashboard.next3Months')}</span>
                  <span className={`font-medium ${
                    seasonal.next_3_months === "High" ? "text-tropical-400" :
                    seasonal.next_3_months === "Low" ? "text-red-400" :
                    "text-ocean-400"
                  }`}>{seasonal.next_3_months}</span>
                </div>
              </div>
            ) : (
              <span className="text-sm text-gray-400">{t('dashboard.noSeasonalData')}</span>
            )}
            </div>
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
