import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { stagger, fadeUp } from "../utils/animations";
import Panel from "../components/layout/Panel";
import ChartContainer from "../components/shared/ChartContainer";
import ExportCSVButton from "../components/shared/ExportCSVButton";
import ForecastChart, {
  type TimeSeriesPoint as ChartPoint,
} from "../components/forecast/ForecastChart";
import ErrorState from "../components/shared/ErrorState";
import { useIndicators, useTimeSeries } from "../api/hooks";

const fallbackIndicators = [
  { id: "turistas", source: "istac", available_from: "2010-01", available_to: "2026-01", total_points: 193 },
  { id: "turistas_extranjeros", source: "istac", available_from: "2010-01", available_to: "2026-01", total_points: 193 },
  { id: "alojatur_ocupacion", source: "istac", available_from: "2009-01", available_to: "2026-01", total_points: 205 },
  { id: "alojatur_adr", source: "istac", available_from: "2009-01", available_to: "2026-01", total_points: 205 },
  { id: "alojatur_revpar", source: "istac", available_from: "2009-01", available_to: "2026-01", total_points: 205 },
  { id: "alojatur_pernoctaciones", source: "istac", available_from: "2009-01", available_to: "2026-01", total_points: 205 },
];

export default function DataExplorerPage() {
  const [selectedIndicator, setSelectedIndicator] = useState<string | null>(null);
  const { data: apiIndicators, error: indicatorsError, refetch: refetchIndicators } = useIndicators();
  const { data: tsData, loading: tsLoading, error: tsError, refetch: refetchTs } = useTimeSeries(
    selectedIndicator || ""
  );

  const indicators = apiIndicators || fallbackIndicators;

  const chartData = useMemo<ChartPoint[]>(() => {
    if (!tsData?.data) return [];
    return tsData.data.map((d) => ({
      date: new Date(d.period + "-01"),
      value: d.value,
    }));
  }, [tsData]);

  const csvRows = useMemo<(string | number)[][]>(() => {
    if (!tsData?.data || !selectedIndicator) return [];
    return tsData.data.map((d) => [selectedIndicator, d.period, d.value]);
  }, [tsData, selectedIndicator]);

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold gradient-text">Data Explorer</h1>
          <p className="text-sm text-gray-400 mt-1">
            Browse raw time series and indicators
          </p>
        </div>
        <ExportCSVButton
          headers={["Indicator", "Period", "Value"]}
          rows={csvRows}
          filename={`data-explorer-${selectedIndicator || "none"}`}
          metadata={{
            source: "Tenerife Tourism Intelligence - Data Explorer",
            filters: selectedIndicator
              ? { indicator: selectedIndicator }
              : undefined,
          }}
          disabled={!selectedIndicator || csvRows.length === 0}
          ariaLabel="Export time series data as CSV"
        />
      </motion.div>

      <motion.div variants={fadeUp}>
        <Panel title="Available Indicators">
          {indicatorsError ? (
            <ErrorState message="Could not load indicators." onRetry={refetchIndicators} />
          ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-700/50">
                  <th scope="col" className="pb-3 font-medium">Indicator</th>
                  <th scope="col" className="pb-3 font-medium">Source</th>
                  <th scope="col" className="pb-3 font-medium">Range</th>
                  <th scope="col" className="pb-3 font-medium">Points</th>
                  <th scope="col" className="pb-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {indicators.map((ind) => (
                  <tr
                    key={ind.id}
                    className={`border-b border-gray-800/30 hover:bg-gray-800/30 transition-colors ${
                      selectedIndicator === ind.id ? "bg-ocean-500/10" : ""
                    }`}
                  >
                    <td className="py-3 text-gray-200 font-mono text-xs">
                      {ind.id}
                    </td>
                    <td className="py-3 text-gray-400">{ind.source}</td>
                    <td className="py-3 text-gray-400 font-mono text-xs">
                      {ind.available_from} \u2192 {ind.available_to}
                    </td>
                    <td className="py-3 text-gray-400 text-center">
                      {ind.total_points}
                    </td>
                    <td className="py-3">
                      <button
                        onClick={() =>
                          setSelectedIndicator(
                            selectedIndicator === ind.id ? null : ind.id
                          )
                        }
                        aria-label={`${selectedIndicator === ind.id ? "Deselect" : "View"} ${ind.id}`}
                        aria-pressed={selectedIndicator === ind.id}
                        className={`px-3 py-1 text-xs rounded transition-colors ${
                          selectedIndicator === ind.id
                            ? "bg-ocean-600 text-white"
                            : "bg-ocean-600/20 text-ocean-400 hover:bg-ocean-600/30"
                        }`}
                      >
                        {selectedIndicator === ind.id ? "Selected" : "View"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          )}
        </Panel>
      </motion.div>

      <motion.div variants={fadeUp}>
        <Panel
          title={
            selectedIndicator
              ? `Time Series: ${selectedIndicator}`
              : "Time Series Viewer"
          }
          subtitle={
            selectedIndicator
              ? `${tsData?.metadata?.total_points || 0} data points`
              : "Select an indicator above to visualize"
          }
        >
          {selectedIndicator ? (
            tsError ? (
              <ErrorState message="Could not load time series data." onRetry={refetchTs} />
            ) : tsLoading ? (
              <div className="h-[360px] flex items-center justify-center" role="status" aria-live="polite">
                <div className="w-8 h-8 border-2 border-ocean-500 border-t-transparent rounded-full animate-spin" />
                <span className="sr-only">Loading time series data</span>
              </div>
            ) : chartData.length > 0 ? (
              <ChartContainer height={360}>
                {({ width, height }) => (
                  <ForecastChart
                    historical={chartData}
                    forecast={[]}
                    width={width}
                    height={height}
                    yLabel={selectedIndicator}
                  />
                )}
              </ChartContainer>
            ) : (
              <div className="h-[360px] flex items-center justify-center text-gray-400">
                <p className="text-sm">No data available for this indicator</p>
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
                <p className="text-sm">Select an indicator to view its time series</p>
              </div>
            </div>
          )}
        </Panel>
      </motion.div>
    </motion.div>
  );
}
