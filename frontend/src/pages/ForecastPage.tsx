import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Panel from "../components/layout/Panel";
import ChartContainer from "../components/shared/ChartContainer";
import ExportCSVButton from "../components/shared/ExportCSVButton";
import ForecastChart, {
  generateMockData,
  type TimeSeriesPoint as ChartTimePoint,
  type ForecastPoint as ChartForecastPoint,
} from "../components/forecast/ForecastChart";
import ScenarioChart, {
  ScenarioImpactStats,
} from "../components/forecast/ScenarioChart";
import YoYHeatmap from "../components/forecast/YoYHeatmap";
import ErrorBoundary from "../components/shared/ErrorBoundary";
import {
  useTimeSeries,
  usePredictions,
  usePredictionCompare,
  useScenarios,
  type ScenarioInput,
  type ModelAccuracyMetrics,
} from "../api/hooks";

const stagger = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

export default function ForecastPage() {
  const mockData = useMemo(() => generateMockData(), []);

  // Real API data (will fail gracefully if backend not running)
  const { data: tsData } = useTimeSeries("turistas");
  const { data: predData } = usePredictions();
  const { data: scenarioData, runScenario, loading: scenarioLoading, error: scenarioError } = useScenarios();
  const { data: compareData, loading: compareLoading } = usePredictionCompare();

  // Determine if we are using mock data (backend unavailable)
  const isMockData = !tsData?.data || !predData?.forecast;

  // Build model list from compare API or fall back to hardcoded data
  const modelList = useMemo(() => {
    const metricsMap = compareData?.metrics ?? {};

    if (compareData?.models) {
      const entries = Object.entries(compareData.models).map(([key, points]) => ({
        key,
        name: key
          .split("_")
          .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
          .join(" "),
        periods: points.length,
        active: points.length > 0,
        best: false,
        metrics: metricsMap[key] ?? null,
      }));

      // Mark the model with the lowest MAPE as best
      const modelsWithMape = entries.filter((e) => e.metrics?.mape != null);
      if (modelsWithMape.length > 0) {
        const minMape = Math.min(...modelsWithMape.map((e) => e.metrics!.mape));
        const bestIdx = entries.findIndex((e) => e.metrics?.mape === minMape);
        if (bestIdx >= 0) entries[bestIdx].best = true;
      } else if (entries.length > 0) {
        // Fallback: mark model with most periods
        const maxPeriods = Math.max(...entries.map((e) => e.periods));
        const bestIdx = entries.findIndex((e) => e.periods === maxPeriods);
        if (bestIdx >= 0) entries[bestIdx].best = true;
      }
      return entries;
    }
    // Fallback hardcoded data
    return [
      { key: "sarima", name: "SARIMA", periods: 12, active: true, best: false, metrics: null as ModelAccuracyMetrics | null },
      { key: "holt_winters", name: "Holt-Winters", periods: 12, active: false, best: false, metrics: null },
      { key: "ensemble", name: "Ensemble", periods: 12, active: true, best: true, metrics: null },
      { key: "seasonal_naive", name: "Seasonal Naive", periods: 12, active: false, best: false, metrics: null },
    ];
  }, [compareData]);

  // Scenario sliders state
  const [scenarioValues, setScenarioValues] = useState({
    occupancy_change_pct: 0,
    adr_change_pct: 0,
    foreign_ratio_change_pct: 0,
  });

  // Convert API data to chart format, fallback to mock
  const chartData = useMemo(() => {
    if (tsData?.data && predData?.forecast) {
      const historical: ChartTimePoint[] = tsData.data.map((d) => ({
        date: new Date(d.period + "-01"),
        value: d.value,
      }));
      const forecast: ChartForecastPoint[] = predData.forecast.map((d) => ({
        date: new Date(d.period + "-01"),
        value: d.value,
        ci80Lower: d.ci_lower_80,
        ci80Upper: d.ci_upper_80,
        ci95Lower: d.ci_lower_95,
        ci95Upper: d.ci_upper_95,
      }));
      return { historical, forecast };
    }
    return mockData;
  }, [tsData, predData, mockData]);

  const forecastCsvRows = useMemo<(string | number)[][]>(() => {
    if (!predData?.forecast) return [];
    return predData.forecast.map((d) => [
      d.period,
      d.value,
      d.ci_lower_80,
      d.ci_upper_80,
      d.ci_lower_95,
      d.ci_upper_95,
    ]);
  }, [predData]);

  const handleRunScenario = () => {
    runScenario(scenarioValues as ScenarioInput);
  };

  const updateSlider = (key: keyof typeof scenarioValues, value: number) => {
    setScenarioValues((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold gradient-text">Prediction Engine</h2>
          <p className="text-sm text-gray-500 mt-1">
            AI-powered tourism demand forecasting
          </p>
        </div>
        <ExportCSVButton
          headers={["Period", "Forecast", "CI Lower 80", "CI Upper 80", "CI Lower 95", "CI Upper 95"]}
          rows={forecastCsvRows}
          filename={`forecast-${predData?.model_info?.name || "ensemble"}`}
          metadata={{
            source: "Tenerife Tourism Intelligence - Prediction Engine",
            filters: {
              model: predData?.model_info?.name || "ensemble",
              periods: String(predData?.model_info?.total_periods || 12),
            },
          }}
          disabled={forecastCsvRows.length === 0}
          ariaLabel="Export forecast data as CSV"
        />
      </motion.div>

      {/* Mock data warning banner */}
      {isMockData && (
        <motion.div
          variants={fadeUp}
          className="flex items-start gap-3 p-4 rounded-lg border border-amber-600/50 bg-amber-900/20"
          role="alert"
        >
          <svg
            className="w-5 h-5 text-amber-400 mt-0.5 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
            />
          </svg>
          <div>
            <p className="text-sm font-semibold text-amber-300">
              Demo data -- the connection to the prediction server is not available
            </p>
            <p className="text-xs text-amber-400/70 mt-1">
              The charts below display synthetic data for demonstration purposes only.
              Values shown are not based on real predictions.
            </p>
          </div>
        </motion.div>
      )}

      {/* Main chart */}
      <motion.div variants={fadeUp}>
        <Panel
          title="Forecast Chart"
          subtitle="Historical arrivals + predicted values with 80%/95% confidence bands -- Tenerife peaks Nov-Mar (winter high season)"
        >
          <ErrorBoundary>
            <div className={isMockData ? "relative" : ""}>
              {isMockData && (
                <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
                  <span className="text-3xl font-bold text-white/[0.07] rotate-[-18deg] select-none tracking-widest uppercase">
                    Demo Data
                  </span>
                </div>
              )}
              <div
                className={
                  isMockData
                    ? "border border-dashed border-amber-600/30 rounded-lg p-1 opacity-75 grayscale-[40%]"
                    : ""
                }
              >
                <ChartContainer height={380}>
                  {({ width, height }) => (
                    <ForecastChart
                      historical={chartData.historical}
                      forecast={chartData.forecast}
                      width={width}
                      height={height}
                      yLabel="Tourist Arrivals"
                      isMock={isMockData}
                    />
                  )}
                </ChartContainer>
              </div>
            </div>
          </ErrorBoundary>
        </Panel>
      </motion.div>

      {/* Scenario + Model perf */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <motion.div variants={fadeUp}>
          <Panel
            title="Scenario Engine"
            subtitle="Adjust parameters for what-if analysis"
          >
            <div className="space-y-5 py-2">
              {[
                { label: "Occupancy Change", key: "occupancy_change_pct" as const },
                { label: "ADR Change", key: "adr_change_pct" as const },
                { label: "Foreign Tourist Ratio", key: "foreign_ratio_change_pct" as const },
              ].map(({ label, key }) => (
                <div key={key}>
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-gray-400">{label}</span>
                    <span className="text-ocean-400 font-mono">
                      {scenarioValues[key] > 0 ? "+" : ""}
                      {scenarioValues[key]}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min={-20}
                    max={20}
                    value={scenarioValues[key]}
                    onChange={(e) => updateSlider(key, Number(e.target.value))}
                    className="w-full h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-ocean-500"
                  />
                </div>
              ))}
              <button
                onClick={handleRunScenario}
                disabled={scenarioLoading}
                className="w-full py-2.5 bg-ocean-600 hover:bg-ocean-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
              >
                {scenarioLoading ? "Running..." : "Run Scenario"}
              </button>
              {scenarioError && (
                <div className="mt-3 p-3 bg-red-900/30 border border-red-700/50 rounded-lg">
                  <p className="text-sm text-red-400">
                    <span className="font-medium">Scenario error:</span>{" "}
                    {scenarioError}
                  </p>
                </div>
              )}
            </div>
          </Panel>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Panel
            title="Model Performance"
            subtitle="Forecasting model comparison -- lower MAPE = better accuracy"
          >
            <div className="space-y-3 py-2">
              {compareLoading ? (
                <>
                  {[0, 1, 2, 3].map((i) => (
                    <div
                      key={i}
                      className="h-10 rounded-lg bg-gray-800/40 animate-pulse"
                    />
                  ))}
                </>
              ) : (
                modelList.map(({ name, periods, active, best, metrics }) => (
                  <div
                    key={name}
                    className={`flex items-center justify-between py-2.5 px-3 rounded-lg ${
                      best
                        ? "bg-tropical-500/10 ring-1 ring-tropical-500/30"
                        : "bg-gray-800/40"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <div
                        className={`w-2 h-2 rounded-full ${active ? "bg-tropical-500" : "bg-gray-600"}`}
                      />
                      <span className="text-sm text-gray-300">{name}</span>
                      {best && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-tropical-500/20 text-tropical-400 font-medium">
                          Best
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      {metrics ? (
                        <span
                          className={`text-xs font-mono px-2 py-0.5 rounded ${
                            best
                              ? "bg-tropical-500/20 text-tropical-300"
                              : "bg-gray-700/60 text-gray-400"
                          }`}
                          title={`RMSE: ${metrics.rmse.toLocaleString()} | MAE: ${metrics.mae.toLocaleString()} | MAPE: ${metrics.mape.toFixed(1)}% | Test: ${metrics.test_size} months`}
                        >
                          MAPE {metrics.mape.toFixed(1)}%
                        </span>
                      ) : (
                        <span className="text-sm font-mono text-gray-400">
                          {periods} periods
                        </span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </Panel>
        </motion.div>
      </div>

      {/* Scenario Results */}
      <AnimatePresence>
        {scenarioData && (
          <motion.div
            variants={fadeUp}
            initial="hidden"
            animate="show"
            exit={{ opacity: 0, y: -8, transition: { duration: 0.3 } }}
          >
            <Panel
              title="Scenario Comparison"
              subtitle="Baseline vs scenario forecast -- shaded areas show positive (green) and negative (red) impact"
            >
              <ChartContainer height={340}>
                {({ width, height }) => (
                  <ScenarioChart
                    data={scenarioData}
                    width={width}
                    height={height}
                  />
                )}
              </ChartContainer>
              <ScenarioImpactStats data={scenarioData} />
            </Panel>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Heatmap */}
      <motion.div variants={fadeUp}>
        <Panel
          title="YoY Heatmap"
          subtitle="Month x Year comparison -- hover any cell for details"
        >
          <ErrorBoundary>
            <ChartContainer height={280}>
              {({ width, height }) => (
                <YoYHeatmap width={width} height={height} />
              )}
            </ChartContainer>
          </ErrorBoundary>
        </Panel>
      </motion.div>
    </motion.div>
  );
}
