import { useState, useMemo, useCallback } from "react";
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
import { useIndicators, useTimeSeries } from "../api/hooks";

const MAX_INDICATORS = 3;

const SERIES_COLORS = ["#1aa0d2", "#28c066", "#f472b6"];

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
  const [selectedIndicators, setSelectedIndicators] = useState<string[]>([]);
  const { data: apiIndicators, error: indicatorsError, refetch: refetchIndicators } = useIndicators();

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
    return tsData.data.map((d) => ({
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
          data: tsData.data,
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
      tsData.data.forEach((d) => {
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
                        <td className="py-3 text-gray-200 font-mono text-xs">
                          <span className="flex items-center gap-2">
                            {selected && (
                              <span
                                className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0"
                                style={{ backgroundColor: SERIES_COLORS[colorIdx] }}
                                aria-hidden="true"
                              />
                            )}
                            {ind.id}
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
                            aria-label={`${selected ? t("dataExplorer.deselect") : t("dataExplorer.view")} ${ind.id}`}
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
              <div className="h-[360px] flex items-center justify-center" role="status" aria-live="polite">
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
    </motion.div>
  );
}
