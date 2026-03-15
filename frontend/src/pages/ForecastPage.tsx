import { useMemo, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useTranslation } from "react-i18next";
import { stagger, fadeUp } from "../utils/animations";
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
import ErrorState from "../components/shared/ErrorState";
import { api } from "../api/client";
import {
  useTimeSeries,
  usePredictions,
  usePredictionCompare,
  useScenarios,
  useSavedScenarios,
  useFeatureImportance,
  useTrainingInfo,
  type ScenarioInput,
  type ScenarioResponse,
  type ScenarioCompareResponse,
  type SavedScenarioSummary,
  type ModelAccuracyMetrics,
} from "../api/hooks";

const COMPARE_COLORS = ["#38bdf8", "#f472b6", "#a78bfa"]; // sky-400, pink-400, violet-400

export default function ForecastPage() {
  const { t, i18n } = useTranslation();
  const mockData = useMemo(() => generateMockData(), []);

  // Real API data (will fail gracefully if backend not running)
  const { data: tsData, error: tsError, refetch: refetchTs } = useTimeSeries("turistas");
  const { data: predData, error: predError, refetch: refetchPred } = usePredictions();
  const { data: scenarioData, runScenario, loading: scenarioLoading, error: scenarioError } = useScenarios();
  const { data: compareData, loading: compareLoading, error: compareError, refetch: refetchCompare } = usePredictionCompare();
  const { data: trainingInfo } = useTrainingInfo();

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

  // Saved scenarios
  const { data: savedScenarios, refetch: refetchSaved } = useSavedScenarios();
  const { data: featureData } = useFeatureImportance();

  // Scenario sliders state
  const [scenarioValues, setScenarioValues] = useState({
    occupancy_change_pct: 0,
    adr_change_pct: 0,
    foreign_ratio_change_pct: 0,
  });

  // Save scenario UI state
  const [showSaveInput, setShowSaveInput] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saving, setSaving] = useState(false);

  // Saved scenarios panel
  const [savedPanelOpen, setSavedPanelOpen] = useState(false);
  const [selectedForCompare, setSelectedForCompare] = useState<number[]>([]);
  const [compareResult, setCompareResult] = useState<ScenarioCompareResponse | null>(null);
  const [comparing, setComparing] = useState(false);

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

  const handleSaveScenario = useCallback(async () => {
    if (!saveName.trim()) return;
    setSaving(true);
    try {
      await api.scenarios.save({
        name: saveName.trim(),
        occupancy_change_pct: scenarioValues.occupancy_change_pct,
        adr_change_pct: scenarioValues.adr_change_pct,
        foreign_ratio_change_pct: scenarioValues.foreign_ratio_change_pct,
        horizon: 12,
      });
      setSaveName("");
      setShowSaveInput(false);
      refetchSaved();
    } catch {
      // Save failed silently -- endpoint may not be available yet
    } finally {
      setSaving(false);
    }
  }, [saveName, scenarioValues, refetchSaved]);

  const handleDeleteScenario = useCallback(async (id: number) => {
    try {
      await api.scenarios.delete(id);
      setSelectedForCompare((prev) => prev.filter((sid) => sid !== id));
      refetchSaved();
    } catch {
      // Delete failed silently
    }
  }, [refetchSaved]);

  const handleLoadScenario = useCallback((s: SavedScenarioSummary) => {
    setScenarioValues({
      occupancy_change_pct: s.occupancy_change_pct,
      adr_change_pct: s.adr_change_pct,
      foreign_ratio_change_pct: s.foreign_ratio_change_pct,
    });
  }, []);

  const toggleCompareSelection = useCallback((id: number) => {
    setSelectedForCompare((prev) => {
      if (prev.includes(id)) return prev.filter((sid) => sid !== id);
      if (prev.length >= 3) return prev;
      return [...prev, id];
    });
  }, []);

  const handleCompare = useCallback(async () => {
    if (selectedForCompare.length < 2) return;
    setComparing(true);
    try {
      const result = (await api.scenarios.compare(selectedForCompare)) as ScenarioCompareResponse;
      setCompareResult(result);
    } catch {
      // Compare failed silently
    } finally {
      setComparing(false);
    }
  }, [selectedForCompare]);

  // Feature importance sorted descending
  const sortedFeatures = useMemo(() => {
    if (!featureData?.features) return [];
    return Object.entries(featureData.features)
      .sort(([, a], [, b]) => b - a);
  }, [featureData]);

  const maxFeatureValue = useMemo(() => {
    if (sortedFeatures.length === 0) return 1;
    return sortedFeatures[0][1] || 1;
  }, [sortedFeatures]);

  const currentLocale = i18n.language?.startsWith("es") ? "es-ES" : "en-GB";

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold gradient-text">{t('forecast.title')}</h1>
          <p className="text-sm text-gray-400 mt-1">
            {t('forecast.subtitle')}
          </p>
          {trainingInfo?.last_trained_at && (
            <p className="text-xs text-gray-500 mt-1">
              {t('forecast.modelTrainedOn')}{" "}
              <time dateTime={trainingInfo.last_trained_at}>
                {new Date(trainingInfo.last_trained_at).toLocaleDateString(currentLocale, {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })}
              </time>
            </p>
          )}
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
          ariaLabel={t('forecast.exportAriaLabel')}
        />
      </motion.div>

      {/* API error banner with retry */}
      {(tsError || predError) && (
        <motion.div variants={fadeUp}>
          <ErrorState
            message={t('forecast.couldNotLoadForecast')}
            onRetry={() => { refetchTs(); refetchPred(); }}
          />
        </motion.div>
      )}

      {/* Mock data warning banner */}
      {isMockData && !tsError && !predError && (
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
              {t('forecast.demoDataWarning')}
            </p>
            <p className="text-xs text-amber-400/70 mt-1">
              {t('forecast.demoDataDetails')}
            </p>
          </div>
        </motion.div>
      )}

      {/* Main chart */}
      <motion.div variants={fadeUp}>
        <Panel
          title={t('forecast.forecastChart')}
          subtitle={t('forecast.forecastChartSubtitle')}
        >
          <ErrorBoundary>
            <div className={isMockData ? "relative" : ""}>
              {isMockData && (
                <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
                  <span className="text-3xl font-bold text-white/[0.07] rotate-[-18deg] select-none tracking-widest uppercase">
                    {t('forecast.demoData')}
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
                      yLabel={t('forecast.touristArrivals')}
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
            title={t('forecast.scenarioEngine')}
            subtitle={t('forecast.scenarioSubtitle')}
          >
            <div className="space-y-5 py-2">
              {[
                { label: t('forecast.occupancyChange'), key: "occupancy_change_pct" as const },
                { label: t('forecast.adrChange'), key: "adr_change_pct" as const },
                { label: t('forecast.foreignTouristRatio'), key: "foreign_ratio_change_pct" as const },
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
                    aria-label={`${label} ${scenarioValues[key] > 0 ? "+" : ""}${scenarioValues[key]}%`}
                    className="w-full h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-ocean-500"
                  />
                </div>
              ))}
              <button
                onClick={handleRunScenario}
                disabled={scenarioLoading}
                className="w-full py-2.5 bg-ocean-600 hover:bg-ocean-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
              >
                {scenarioLoading ? t('forecast.running') : t('forecast.runScenario')}
              </button>
              {scenarioError && (
                <div className="mt-3 p-3 bg-red-900/30 border border-red-700/50 rounded-lg">
                  <p className="text-sm text-red-400">
                    <span className="font-medium">{t('forecast.scenarioError')}:</span>{" "}
                    {scenarioError}
                  </p>
                </div>
              )}

              {/* Save Scenario */}
              {scenarioData && (
                <div className="mt-3">
                  {!showSaveInput ? (
                    <button
                      onClick={() => setShowSaveInput(true)}
                      aria-label={t('forecast.saveScenario')}
                      className="w-full py-2 bg-tropical-600 hover:bg-tropical-500 text-white text-sm font-medium rounded-lg transition-colors"
                    >
                      {t('forecast.saveScenario')}
                    </button>
                  ) : (
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={saveName}
                        onChange={(e) => setSaveName(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter") handleSaveScenario(); }}
                        placeholder={t('forecast.scenarioName')}
                        aria-label={t('forecast.scenarioName')}
                        className="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-tropical-500"
                      />
                      <button
                        onClick={handleSaveScenario}
                        disabled={saving || !saveName.trim()}
                        className="px-4 py-2 bg-tropical-600 hover:bg-tropical-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
                      >
                        {saving ? t('forecast.saving') : t('forecast.saveScenario')}
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Saved Scenarios */}
              <div className="mt-4">
                <button
                  onClick={() => setSavedPanelOpen(!savedPanelOpen)}
                  aria-expanded={savedPanelOpen}
                  aria-label={t('forecast.savedScenarios')}
                  className="flex items-center justify-between w-full text-sm text-gray-400 hover:text-gray-300 transition-colors"
                >
                  <span className="font-medium">{t('forecast.savedScenarios')}</span>
                  <svg
                    className={`w-4 h-4 transition-transform ${savedPanelOpen ? "rotate-180" : ""}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                <AnimatePresence>
                  {savedPanelOpen && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                      className="overflow-hidden"
                    >
                      <div className="mt-2 space-y-2 max-h-48 overflow-y-auto">
                        {(!savedScenarios || savedScenarios.length === 0) ? (
                          <p className="text-xs text-gray-500 py-2">{t('forecast.noSavedScenarios')}</p>
                        ) : (
                          savedScenarios.map((s) => (
                            <div
                              key={s.id}
                              className="flex items-center gap-2 p-2 bg-gray-800/60 rounded-lg group"
                            >
                              <input
                                type="checkbox"
                                checked={selectedForCompare.includes(s.id)}
                                onChange={() => toggleCompareSelection(s.id)}
                                aria-label={`${t('forecast.selectToCompare')}: ${s.name}`}
                                className="w-3.5 h-3.5 rounded border-gray-600 text-ocean-500 focus:ring-ocean-500 bg-gray-700 shrink-0"
                              />
                              <div className="flex-1 min-w-0">
                                <button
                                  onClick={() => handleLoadScenario(s)}
                                  aria-label={`${t('forecast.loadParams')}: ${s.name}`}
                                  className="text-sm text-gray-300 hover:text-white truncate block w-full text-left transition-colors"
                                  title={`Occ: ${s.occupancy_change_pct}% | ADR: ${s.adr_change_pct}% | Foreign: ${s.foreign_ratio_change_pct}%`}
                                >
                                  {s.name}
                                </button>
                                <p className="text-[10px] text-gray-500">
                                  {new Date(s.created_at).toLocaleDateString(currentLocale, { day: "numeric", month: "short" })}
                                  {" | "}
                                  Occ {s.occupancy_change_pct > 0 ? "+" : ""}{s.occupancy_change_pct}%
                                  {" ADR "}{s.adr_change_pct > 0 ? "+" : ""}{s.adr_change_pct}%
                                </p>
                              </div>
                              <button
                                onClick={() => handleDeleteScenario(s.id)}
                                aria-label={`${t('forecast.deleteScenario')}: ${s.name}`}
                                className="p-1 text-gray-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all shrink-0"
                              >
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                              </button>
                            </div>
                          ))
                        )}
                      </div>

                      {selectedForCompare.length >= 2 && (
                        <button
                          onClick={handleCompare}
                          disabled={comparing}
                          className="mt-2 w-full py-2 bg-ocean-600 hover:bg-ocean-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
                          aria-label={t('forecast.compareScenarios')}
                        >
                          {comparing ? t('forecast.comparing') : `${t('forecast.compareScenarios')} (${selectedForCompare.length})`}
                        </button>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </Panel>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Panel
            title={t('forecast.modelPerformance')}
            subtitle={t('forecast.modelPerformanceSubtitle')}
          >
            <div className="space-y-3 py-2">
              {compareError ? (
                <ErrorState message={t('forecast.couldNotLoadModels')} onRetry={refetchCompare} />
              ) : compareLoading ? (
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
                        aria-hidden="true"
                      />
                      <span className="sr-only">{active ? t('forecast.active') : t('forecast.inactive')}:</span>
                      <span className="text-sm text-gray-300">{name}</span>
                      {best && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-tropical-500/20 text-tropical-400 font-medium">
                          {t('forecast.best')}
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
                          {periods} {t('forecast.periods')}
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
              title={t('forecast.scenarioComparison')}
              subtitle={t('forecast.scenarioComparisonSubtitle')}
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

      {/* Compared Scenarios */}
      <AnimatePresence>
        {compareResult && (
          <motion.div
            variants={fadeUp}
            initial="hidden"
            animate="show"
            exit={{ opacity: 0, y: -8, transition: { duration: 0.3 } }}
          >
            <Panel
              title={t('forecast.comparedScenarios')}
              subtitle={`${Object.keys(compareResult.scenarios).length} scenarios`}
            >
              <div className="space-y-4">
                {Object.entries(compareResult.scenarios).map(([id, result], idx) => {
                  const scenario = savedScenarios?.find((s) => s.id === Number(id));
                  const color = COMPARE_COLORS[idx % COMPARE_COLORS.length];
                  return (
                    <div key={id} className="flex items-start gap-3">
                      <div
                        className="w-3 h-3 rounded-full mt-1 shrink-0"
                        style={{ backgroundColor: color }}
                        aria-hidden="true"
                      />
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-300">
                          {scenario?.name || `Scenario #${id}`}
                        </p>
                        <div className="flex gap-4 mt-1 text-xs text-gray-500">
                          {scenario && (
                            <>
                              <span>Occ {scenario.occupancy_change_pct > 0 ? "+" : ""}{scenario.occupancy_change_pct}%</span>
                              <span>ADR {scenario.adr_change_pct > 0 ? "+" : ""}{scenario.adr_change_pct}%</span>
                              <span>Foreign {scenario.foreign_ratio_change_pct > 0 ? "+" : ""}{scenario.foreign_ratio_change_pct}%</span>
                            </>
                          )}
                        </div>
                        {(result as ScenarioResponse).scenario_forecast && (
                          <div className="mt-2">
                            <ChartContainer height={180}>
                              {({ width, height }) => (
                                <ScenarioChart
                                  data={result as ScenarioResponse}
                                  width={width}
                                  height={height}
                                />
                              )}
                            </ChartContainer>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </Panel>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Feature Importance */}
      {sortedFeatures.length > 0 && (
        <motion.div variants={fadeUp}>
          <Panel
            title={t('forecast.featureImportance')}
          >
            <div className="space-y-2 py-1">
              {sortedFeatures.map(([name, value]) => (
                <div key={name} className="flex items-center gap-3">
                  <span className="text-xs text-gray-400 w-32 truncate shrink-0" title={name}>
                    {name}
                  </span>
                  <div className="flex-1 h-4 bg-gray-800 rounded overflow-hidden">
                    <div
                      className="h-full bg-tropical-500/70 rounded transition-all"
                      style={{ width: `${(value / maxFeatureValue) * 100}%` }}
                      role="progressbar"
                      aria-valuenow={Math.round(value * 100)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label={`${name}: ${(value * 100).toFixed(1)}%`}
                    />
                  </div>
                  <span className="text-xs text-gray-500 font-mono w-12 text-right shrink-0">
                    {(value * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          </Panel>
        </motion.div>
      )}

      {/* Heatmap */}
      <motion.div variants={fadeUp}>
        <Panel
          title={t('forecast.yoyHeatmap')}
          subtitle={t('forecast.yoyHeatmapSubtitle')}
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
