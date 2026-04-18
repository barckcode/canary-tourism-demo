import { useState, useMemo, useCallback, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { stagger, fadeUp } from "../utils/animations";
import Panel from "../components/layout/Panel";
import ChartContainer from "../components/shared/ChartContainer";
import ExportCSVButton from "../components/shared/ExportCSVButton";
import ForecastChart, {
  type TimeSeriesPoint as ChartPoint,
} from "../components/forecast/ForecastChart";
import ComparisonChart, {
  type SeriesData,
} from "../components/shared/ComparisonChart";
import ErrorState from "../components/shared/ErrorState";
import { useIndicators, useTimeSeries, useProvinceComparison, useAccommodationComparison } from "../api/hooks";
import { usePageTitle } from "../hooks/usePageTitle";

const MAX_INDICATORS = 3;

const SERIES_COLORS = ["#1aa0d2", "#28c066", "#f472b6"];

const COMPARISON_INDICATORS = [
  { key: "viajeros", labelKey: "dataExplorer.comparison.indicator.viajeros" },
  { key: "pernoctaciones", labelKey: "dataExplorer.comparison.indicator.pernoctaciones" },
  { key: "estancia_media", labelKey: "dataExplorer.comparison.indicator.estancia_media" },
  { key: "ocupacion_plazas", labelKey: "dataExplorer.comparison.indicator.ocupacion_plazas" },
  { key: "adr", labelKey: "dataExplorer.comparison.indicator.adr" },
  { key: "revpar", labelKey: "dataExplorer.comparison.indicator.revpar" },
  { key: "apartamento_ocupacion", labelKey: "dataExplorer.comparison.indicator.apartamentoOcupacion" },
  { key: "apartamento_estancia_media", labelKey: "dataExplorer.comparison.indicator.apartamentoEstancia" },
] as const;

const DISPLAY_PERIODS = 12;

const fallbackIndicators = [
  { id: "turistas", source: "istac", available_from: "2010-01", available_to: "2026-01", total_points: 193 },
  { id: "turistas_extranjeros", source: "istac", available_from: "2010-01", available_to: "2026-01", total_points: 193 },
  { id: "alojatur_ocupacion", source: "istac", available_from: "2009-01", available_to: "2026-01", total_points: 205 },
  { id: "alojatur_adr", source: "istac", available_from: "2009-01", available_to: "2026-01", total_points: 205 },
  { id: "alojatur_revpar", source: "istac", available_from: "2009-01", available_to: "2026-01", total_points: 205 },
  { id: "alojatur_pernoctaciones", source: "istac", available_from: "2009-01", available_to: "2026-01", total_points: 205 },
];

function useMultiTimeSeries(indicators: string[]) {
  const ts0 = useTimeSeries(indicators[0] || "");
  const ts1 = useTimeSeries(indicators[1] || "");
  const ts2 = useTimeSeries(indicators[2] || "");

  const results = useMemo(() => {
    const all = [ts0, ts1, ts2];
    return indicators.map((_, i) => all[i]);
  }, [indicators, ts0, ts1, ts2]);

  const loading = results.some((r) => r?.loading);
  const errors = results
    .map((r, i) => (r?.error ? `${indicators[i]}: ${r.error}` : null))
    .filter(Boolean);

  return { results, loading, errors };
}

export default function DataExplorerPage() {
  const { t } = useTranslation();
  usePageTitle("nav.dataExplorer");
  const [searchParams, setSearchParams] = useSearchParams();

  // Initialize selected indicators from URL params
  const initialIndicators = useMemo(() => {
    const param = searchParams.get("indicator");
    if (!param) return [];
    return param.split(",").filter(Boolean).slice(0, MAX_INDICATORS);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [selectedIndicators, setSelectedIndicators] = useState<string[]>(initialIndicators);
  const { data: apiIndicators, error: indicatorsError, refetch: refetchIndicators } = useIndicators();

  // Sync selected indicators to URL
  useEffect(() => {
    setSearchParams((prev) => {
      if (selectedIndicators.length === 0) {
        prev.delete("indicator");
      } else {
        prev.set("indicator", selectedIndicators.join(","));
      }
      return prev;
    }, { replace: true });
  }, [selectedIndicators, setSearchParams]);

  const { results: tsResults, loading: tsLoading, errors: tsErrors } = useMultiTimeSeries(selectedIndicators);

  const indicators = apiIndicators || fallbackIndicators;

  const toggleIndicator = useCallback((id: string) => {
    setSelectedIndicators((prev) => {
      if (prev.includes(id)) {
        return prev.filter((x) => x !== id);
      }
      if (prev.length >= MAX_INDICATORS) {
        return prev;
      }
      return [...prev, id];
    });
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedIndicators([]);
  }, []);

  // Single-indicator mode: chart data for ForecastChart
  const singleChartData = useMemo<ChartPoint[]>(() => {
    if (selectedIndicators.length !== 1) return [];
    const tsData = tsResults[0]?.data;
    if (!tsData?.data) return [];
    return tsData.data
      .filter((d) => d.value != null)
      .map((d) => ({
        date: new Date(d.period + "-01"),
        value: d.value,
      }));
  }, [selectedIndicators.length, tsResults]);

  // Multi-indicator mode: series data for ComparisonChart
  const comparisonSeries = useMemo<SeriesData[]>(() => {
    if (selectedIndicators.length < 2) return [];
    return selectedIndicators
      .map((name, i) => {
        const tsData = tsResults[i]?.data;
        if (!tsData?.data) return null;
        return {
          name,
          data: tsData.data.filter((d) => d.value != null),
          color: SERIES_COLORS[i],
        };
      })
      .filter((s): s is SeriesData => s !== null);
  }, [selectedIndicators, tsResults]);

  // CSV export data
  const csvRows = useMemo<(string | number)[][]>(() => {
    const rows: (string | number)[][] = [];
    selectedIndicators.forEach((name, i) => {
      const tsData = tsResults[i]?.data;
      if (!tsData?.data) return;
      tsData.data
        .filter((d) => d.value != null)
        .forEach((d) => {
          rows.push([name, d.period, d.value]);
        });
    });
    return rows;
  }, [selectedIndicators, tsResults]);

  const isSelected = (id: string) => selectedIndicators.includes(id);
  const selectionCount = selectedIndicators.length;
  const hasSelection = selectionCount > 0;
  const isMulti = selectionCount >= 2;

  const firstTsData = tsResults[0]?.data;
  const refetchFirstTs = tsResults[0]?.refetch;

  // Panel title and subtitle
  const panelTitle = isMulti
    ? t("dataExplorer.compare")
    : hasSelection
      ? t("dataExplorer.timeSeries", { indicator: selectedIndicators[0] })
      : t("dataExplorer.timeSeriesViewer");

  const panelSubtitle = isMulti
    ? `${selectionCount} ${t("dataExplorer.selectedCount")}`
    : hasSelection
      ? t("dataExplorer.dataPoints", { count: firstTsData?.metadata?.total_points || 0 })
      : t("dataExplorer.selectIndicatorAbove");

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold gradient-text">{t("dataExplorer.title")}</h1>
          <p className="text-sm text-gray-400 mt-1">
            {t("dataExplorer.subtitle")}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {hasSelection && (
            <button
              onClick={clearSelection}
              className="px-3 py-1.5 text-xs rounded bg-gray-700/50 text-gray-300 hover:bg-gray-700 transition-colors"
              aria-label={t("dataExplorer.clearSelection")}
            >
              {t("dataExplorer.clearSelection")}
            </button>
          )}
          <ExportCSVButton
            headers={[t("dataExplorer.indicator"), "Period", t("dashboard.value")]}
            rows={csvRows}
            filename={`data-explorer-${selectedIndicators.join("-") || "none"}`}
            metadata={{
              source: "Tenerife Tourism Intelligence - Data Explorer",
              filters: hasSelection
                ? { indicators: selectedIndicators.join(", ") }
                : undefined,
            }}
            disabled={!hasSelection || csvRows.length === 0}
            ariaLabel={t("dataExplorer.exportAriaLabel")}
          />
        </div>
      </motion.div>

      <motion.div variants={fadeUp}>
        <Panel title={t("dataExplorer.availableIndicators")}>
          {indicatorsError ? (
            <ErrorState message={t("dataExplorer.couldNotLoadIndicators")} onRetry={refetchIndicators} />
          ) : (
          <>
            {selectionCount > 0 && (
              <div className="mb-3 flex items-center gap-2 text-xs text-gray-400">
                <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-ocean-600/20 text-ocean-400">
                  {selectionCount} {t("dataExplorer.selectedCount")}
                </span>
                {selectionCount >= MAX_INDICATORS && (
                  <span className="text-gray-500">
                    {t("dataExplorer.maxIndicators")}
                  </span>
                )}
              </div>
            )}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <caption className="sr-only">{t("dataExplorer.tableCaption")}</caption>
                <thead>
                  <tr className="text-left text-gray-400 border-b border-gray-700/50">
                    <th scope="col" className="pb-3 font-medium">{t("dataExplorer.indicator")}</th>
                    <th scope="col" className="pb-3 font-medium">{t("dataExplorer.source")}</th>
                    <th scope="col" className="pb-3 font-medium">{t("dataExplorer.range")}</th>
                    <th scope="col" className="pb-3 font-medium">{t("dataExplorer.points")}</th>
                    <th scope="col" className="pb-3 font-medium">{t("dataExplorer.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {indicators.map((ind) => {
                    const selected = isSelected(ind.id);
                    const colorIdx = selectedIndicators.indexOf(ind.id);
                    const atMax = selectionCount >= MAX_INDICATORS && !selected;

                    return (
                      <tr
                        key={ind.id}
                        className={`border-b border-gray-800/30 hover:bg-gray-800/30 transition-colors ${
                          selected ? "bg-ocean-500/10" : ""
                        }`}
                      >
                        <td className="py-3 text-gray-200 text-xs">
                          <span className="flex items-center gap-2">
                            {selected && (
                              <span
                                className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0"
                                style={{ backgroundColor: SERIES_COLORS[colorIdx] }}
                                aria-hidden="true"
                              />
                            )}
                            <span>
                              {t(`indicators.${ind.id}`) !== `indicators.${ind.id}` ? t(`indicators.${ind.id}`) : ind.id}
                            </span>
                          </span>
                        </td>
                        <td className="py-3 text-gray-400">{ind.source}</td>
                        <td className="py-3 text-gray-400 font-mono text-xs">
                          {ind.available_from} {"\u2192"} {ind.available_to}
                        </td>
                        <td className="py-3 text-gray-400 text-center">
                          {ind.total_points}
                        </td>
                        <td className="py-3">
                          <button
                            onClick={() => toggleIndicator(ind.id)}
                            disabled={atMax}
                            aria-label={`${selected ? t("dataExplorer.deselect") : t("dataExplorer.view")}: ${t(`indicators.${ind.id}`) !== `indicators.${ind.id}` ? t(`indicators.${ind.id}`) : ind.id}`}
                            aria-pressed={selected}
                            className={`px-3 py-1 text-xs rounded transition-colors ${
                              selected
                                ? "bg-ocean-600 text-white"
                                : atMax
                                  ? "bg-gray-800/30 text-gray-600 cursor-not-allowed"
                                  : "bg-ocean-600/20 text-ocean-400 hover:bg-ocean-600/30"
                            }`}
                          >
                            {selected ? t("dataExplorer.selected") : t("dataExplorer.view")}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
          )}
        </Panel>
      </motion.div>

      <motion.div variants={fadeUp}>
        <Panel title={panelTitle} subtitle={panelSubtitle}>
          {hasSelection ? (
            tsErrors.length > 0 ? (
              <ErrorState
                message={tsErrors[0] || t("dataExplorer.couldNotLoadTimeSeries")}
                onRetry={refetchFirstTs}
              />
            ) : tsLoading ? (
              <div className="h-[360px] flex items-center justify-center" role="status" aria-live="polite" aria-busy="true">
                <div className="w-8 h-8 border-2 border-ocean-500 border-t-transparent rounded-full animate-spin" />
                <span className="sr-only">{t("common.loadingTimeSeries")}</span>
              </div>
            ) : isMulti && comparisonSeries.length >= 2 ? (
              <ChartContainer height={360}>
                {({ width, height }) => (
                  <ComparisonChart
                    series={comparisonSeries}
                    width={width}
                    height={height}
                  />
                )}
              </ChartContainer>
            ) : singleChartData.length > 0 ? (
              <ChartContainer height={360}>
                {({ width, height }) => (
                  <ForecastChart
                    historical={singleChartData}
                    forecast={[]}
                    width={width}
                    height={height}
                    yLabel={selectedIndicators[0]}
                  />
                )}
              </ChartContainer>
            ) : (
              <div className="h-[360px] flex items-center justify-center text-gray-400">
                <p className="text-sm">{t("dataExplorer.noDataForIndicator")}</p>
              </div>
            )
          ) : (
            <div className="h-[360px] flex items-center justify-center text-gray-400">
              <div className="text-center">
                <svg
                  className="w-12 h-12 mx-auto mb-3 text-gray-700"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1}
                    d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"
                  />
                </svg>
                <p className="text-sm">{t("dataExplorer.selectIndicator")}</p>
              </div>
            </div>
          )}
        </Panel>
      </motion.div>

      <ProvinceComparisonSection />

      <AccommodationComparisonSection />
    </motion.div>
  );
}

function ProvinceComparisonSection() {
  const { t } = useTranslation();
  const [comparisonIndicator, setComparisonIndicator] = useState<string>("pernoctaciones");
  const { data: comparisonData, loading: comparisonLoading, error: comparisonError, refetch: refetchComparison } = useProvinceComparison(comparisonIndicator, 24);

  const es709Data = comparisonData?.provinces?.ES709;
  const es701Data = comparisonData?.provinces?.ES701;

  const displayRows = useMemo(() => {
    if (!es709Data?.data || !es701Data?.data) return [];
    const es709Map = new Map(es709Data.data.map((d) => [d.period, d.value]));
    const es701Map = new Map(es701Data.data.map((d) => [d.period, d.value]));
    const allPeriods = [...new Set([...es709Data.data.map((d) => d.period), ...es701Data.data.map((d) => d.period)])].sort().reverse();
    return allPeriods.slice(0, DISPLAY_PERIODS).map((period) => {
      const v709 = es709Map.get(period);
      const v701 = es701Map.get(period);
      const diff = v709 != null && v701 != null ? v709 - v701 : null;
      return { period, v709, v701, diff };
    });
  }, [es709Data, es701Data]);

  const summaryKpis = useMemo(() => {
    if (displayRows.length === 0) return null;
    const latest = displayRows[0];

    // Find YoY: same month from previous year
    const latestMonth = latest.period.slice(5);
    const prevYearPeriod = `${Number(latest.period.slice(0, 4)) - 1}-${latestMonth}`;
    const prevRow = displayRows.find((r) => r.period === prevYearPeriod);

    const yoy709 = latest.v709 != null && prevRow?.v709 != null && prevRow.v709 !== 0
      ? ((latest.v709 - prevRow.v709) / prevRow.v709) * 100
      : null;
    const yoy701 = latest.v701 != null && prevRow?.v701 != null && prevRow.v701 !== 0
      ? ((latest.v701 - prevRow.v701) / prevRow.v701) * 100
      : null;

    const leading = latest.v709 != null && latest.v701 != null
      ? latest.v709 >= latest.v701 ? "ES709" : "ES701"
      : null;

    return { latest, yoy709, yoy701, leading };
  }, [displayRows]);

  return (
    <motion.div variants={fadeUp}>
      <Panel title={t("dataExplorer.comparison.title")}>
        {/* Indicator selector */}
        <div className="flex flex-wrap gap-2 mb-6" role="tablist" aria-label={t("dataExplorer.comparison.title")}>
          {COMPARISON_INDICATORS.map((ind) => (
            <button
              key={ind.key}
              role="tab"
              aria-selected={comparisonIndicator === ind.key}
              onClick={() => setComparisonIndicator(ind.key)}
              className={`px-4 py-2 text-sm rounded-lg transition-colors ${
                comparisonIndicator === ind.key
                  ? "bg-ocean-600 text-white"
                  : "bg-gray-800/50 text-gray-400 hover:bg-gray-700/50 hover:text-gray-200"
              }`}
            >
              {t(ind.labelKey)}
            </button>
          ))}
        </div>

        {comparisonError ? (
          <ErrorState message={t("dataExplorer.comparison.couldNotLoad")} onRetry={refetchComparison} />
        ) : comparisonLoading ? (
          <div className="h-48 flex items-center justify-center" role="status" aria-live="polite" aria-busy="true">
            <div className="w-8 h-8 border-2 border-ocean-500 border-t-transparent rounded-full animate-spin" />
            <span className="sr-only">{t("common.loading")}</span>
          </div>
        ) : displayRows.length === 0 ? (
          <div className="h-48 flex items-center justify-center text-gray-400">
            <p className="text-sm">{t("common.noDataAvailable")}</p>
          </div>
        ) : (
          <>
            {/* Summary KPIs */}
            {summaryKpis && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                <div className="bg-gray-800/50 rounded-lg p-4">
                  <p className="text-xs text-gray-400 mb-1">{t("dataExplorer.comparison.scTenerife")}</p>
                  <p className="text-xl font-bold text-white">
                    {summaryKpis.latest.v709 != null ? summaryKpis.latest.v709.toLocaleString() : "-"}
                  </p>
                  {summaryKpis.yoy709 != null && (
                    <p className={`text-xs mt-1 ${summaryKpis.yoy709 >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {summaryKpis.yoy709 >= 0 ? "+" : ""}{summaryKpis.yoy709.toFixed(1)}% {t("dataExplorer.comparison.yoyChange")}
                    </p>
                  )}
                </div>
                <div className="bg-gray-800/50 rounded-lg p-4">
                  <p className="text-xs text-gray-400 mb-1">{t("dataExplorer.comparison.lasPalmas")}</p>
                  <p className="text-xl font-bold text-white">
                    {summaryKpis.latest.v701 != null ? summaryKpis.latest.v701.toLocaleString() : "-"}
                  </p>
                  {summaryKpis.yoy701 != null && (
                    <p className={`text-xs mt-1 ${summaryKpis.yoy701 >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {summaryKpis.yoy701 >= 0 ? "+" : ""}{summaryKpis.yoy701.toFixed(1)}% {t("dataExplorer.comparison.yoyChange")}
                    </p>
                  )}
                </div>
                <div className="bg-gray-800/50 rounded-lg p-4">
                  <p className="text-xs text-gray-400 mb-1">{t("dataExplorer.comparison.leading")}</p>
                  <p className="text-xl font-bold text-white">
                    {summaryKpis.leading === "ES709"
                      ? t("dataExplorer.comparison.scTenerife")
                      : summaryKpis.leading === "ES701"
                        ? t("dataExplorer.comparison.lasPalmas")
                        : "-"}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {t("dataExplorer.comparison.latest")}: {summaryKpis.latest.period}
                  </p>
                </div>
              </div>
            )}

            {/* Comparison table */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <caption className="sr-only">{t("dataExplorer.comparison.tableCaption")}</caption>
                <thead>
                  <tr className="text-left text-gray-400 border-b border-gray-700/50">
                    <th scope="col" className="pb-3 font-medium">{t("dataExplorer.comparison.period")}</th>
                    <th scope="col" className="pb-3 font-medium text-right">{t("dataExplorer.comparison.scTenerife")}</th>
                    <th scope="col" className="pb-3 font-medium text-right">{t("dataExplorer.comparison.lasPalmas")}</th>
                    <th scope="col" className="pb-3 font-medium text-right">{t("dataExplorer.comparison.difference")}</th>
                  </tr>
                </thead>
                <tbody>
                  {displayRows.map((row, i) => (
                    <tr
                      key={row.period}
                      className={`border-b border-gray-800/30 ${
                        i % 2 === 0 ? "bg-gray-800/20" : ""
                      }`}
                    >
                      <td className="py-2.5 text-gray-300 font-mono text-xs">{row.period}</td>
                      <td className="py-2.5 text-gray-200 text-right font-mono text-xs">
                        {row.v709 != null ? row.v709.toLocaleString() : "-"}
                      </td>
                      <td className="py-2.5 text-gray-200 text-right font-mono text-xs">
                        {row.v701 != null ? row.v701.toLocaleString() : "-"}
                      </td>
                      <td className={`py-2.5 text-right font-mono text-xs ${
                        row.diff != null
                          ? row.diff >= 0 ? "text-emerald-400" : "text-red-400"
                          : "text-gray-500"
                      }`}>
                        {row.diff != null
                          ? `${row.diff >= 0 ? "+" : ""}${row.diff.toLocaleString()}`
                          : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Panel>
    </motion.div>
  );
}

const ACCOMMODATION_INDICATORS = [
  { key: "viajeros", labelKey: "dataExplorer.accommodation.indicator.viajeros" },
  { key: "pernoctaciones", labelKey: "dataExplorer.accommodation.indicator.pernoctaciones" },
  { key: "plazas", labelKey: "dataExplorer.accommodation.indicator.plazas" },
] as const;

function AccommodationComparisonSection() {
  const { t } = useTranslation();
  const [indicator, setIndicator] = useState<string>("pernoctaciones");
  const { data, loading, error, refetch } = useAccommodationComparison(indicator, 24);

  const ruralData = data?.types?.rural;
  const hotelData = data?.types?.hotel;

  const displayRows = useMemo(() => {
    if (!ruralData?.data || !hotelData?.data) return [];
    const ruralMap = new Map(ruralData.data.map((d) => [d.period, d.value]));
    const hotelMap = new Map(hotelData.data.map((d) => [d.period, d.value]));
    const allPeriods = [...new Set([...ruralData.data.map((d) => d.period), ...hotelData.data.map((d) => d.period)])].sort().reverse();
    return allPeriods.slice(0, DISPLAY_PERIODS).map((period) => {
      const rural = ruralMap.get(period);
      const hotel = hotelMap.get(period);
      const ruralShare = rural != null && hotel != null && hotel !== 0 ? (rural / hotel) * 100 : null;
      return { period, rural, hotel, ruralShare };
    });
  }, [ruralData, hotelData]);

  const summaryKpis = useMemo(() => {
    if (displayRows.length === 0) return null;
    const latest = displayRows[0];
    const ruralShare = latest.rural != null && latest.hotel != null && latest.hotel !== 0
      ? (latest.rural / latest.hotel) * 100
      : null;
    return { latest, ruralShare };
  }, [displayRows]);

  return (
    <motion.div variants={fadeUp}>
      <Panel title={t("dataExplorer.accommodation.title")}>
        {/* Indicator selector */}
        <div className="flex flex-wrap gap-2 mb-6" role="tablist" aria-label={t("dataExplorer.accommodation.title")}>
          {ACCOMMODATION_INDICATORS.map((ind) => (
            <button
              key={ind.key}
              role="tab"
              aria-selected={indicator === ind.key}
              onClick={() => setIndicator(ind.key)}
              className={`px-4 py-2 text-sm rounded-lg transition-colors ${
                indicator === ind.key
                  ? "bg-ocean-600 text-white"
                  : "bg-gray-800/50 text-gray-400 hover:bg-gray-700/50 hover:text-gray-200"
              }`}
            >
              {t(ind.labelKey)}
            </button>
          ))}
        </div>

        {error ? (
          <ErrorState message={t("dataExplorer.accommodation.couldNotLoad")} onRetry={refetch} />
        ) : loading ? (
          <div className="h-48 flex items-center justify-center" role="status" aria-live="polite" aria-busy="true">
            <div className="w-8 h-8 border-2 border-ocean-500 border-t-transparent rounded-full animate-spin" />
            <span className="sr-only">{t("common.loading")}</span>
          </div>
        ) : displayRows.length === 0 ? (
          <div className="h-48 flex items-center justify-center text-gray-400">
            <p className="text-sm">{t("common.noDataAvailable")}</p>
          </div>
        ) : (
          <>
            {/* Summary KPIs */}
            {summaryKpis && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                <div className="bg-gray-800/50 rounded-lg p-4">
                  <p className="text-xs text-gray-400 mb-1">{t("dataExplorer.accommodation.rural")}</p>
                  <p className="text-xl font-bold text-white">
                    {summaryKpis.latest.rural != null ? summaryKpis.latest.rural.toLocaleString() : "-"}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {summaryKpis.latest.period}
                  </p>
                </div>
                <div className="bg-gray-800/50 rounded-lg p-4">
                  <p className="text-xs text-gray-400 mb-1">{t("dataExplorer.accommodation.hotel")}</p>
                  <p className="text-xl font-bold text-white">
                    {summaryKpis.latest.hotel != null ? summaryKpis.latest.hotel.toLocaleString() : "-"}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {summaryKpis.latest.period}
                  </p>
                </div>
                <div className="bg-gray-800/50 rounded-lg p-4">
                  <p className="text-xs text-gray-400 mb-1">{t("dataExplorer.accommodation.ruralShare")}</p>
                  <p className="text-xl font-bold text-white">
                    {summaryKpis.ruralShare != null ? `${summaryKpis.ruralShare.toFixed(1)}%` : "-"}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {t("dataExplorer.accommodation.rural")} / {t("dataExplorer.accommodation.hotel")}
                  </p>
                </div>
              </div>
            )}

            {/* Comparison table */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <caption className="sr-only">{t("dataExplorer.accommodation.tableCaption")}</caption>
                <thead>
                  <tr className="text-left text-gray-400 border-b border-gray-700/50">
                    <th scope="col" className="pb-3 font-medium">{t("dataExplorer.comparison.period")}</th>
                    <th scope="col" className="pb-3 font-medium text-right">{t("dataExplorer.accommodation.rural")}</th>
                    <th scope="col" className="pb-3 font-medium text-right">{t("dataExplorer.accommodation.hotel")}</th>
                    <th scope="col" className="pb-3 font-medium text-right">{t("dataExplorer.accommodation.ruralShare")}</th>
                  </tr>
                </thead>
                <tbody>
                  {displayRows.map((row, i) => (
                    <tr
                      key={row.period}
                      className={`border-b border-gray-800/30 ${
                        i % 2 === 0 ? "bg-gray-800/20" : ""
                      }`}
                    >
                      <td className="py-2.5 text-gray-300 font-mono text-xs">{row.period}</td>
                      <td className="py-2.5 text-gray-200 text-right font-mono text-xs">
                        {row.rural != null ? row.rural.toLocaleString() : "-"}
                      </td>
                      <td className="py-2.5 text-gray-200 text-right font-mono text-xs">
                        {row.hotel != null ? row.hotel.toLocaleString() : "-"}
                      </td>
                      <td className="py-2.5 text-gray-400 text-right font-mono text-xs">
                        {row.ruralShare != null ? `${row.ruralShare.toFixed(1)}%` : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Panel>
    </motion.div>
  );
}
