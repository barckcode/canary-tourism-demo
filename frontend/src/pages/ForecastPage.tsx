import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import Panel from "../components/layout/Panel";
import ChartContainer from "../components/shared/ChartContainer";
import ForecastChart, {
  generateMockData,
  type TimeSeriesPoint as ChartTimePoint,
  type ForecastPoint as ChartForecastPoint,
} from "../components/forecast/ForecastChart";
import YoYHeatmap from "../components/forecast/YoYHeatmap";
import {
  useTimeSeries,
  usePredictions,
  useScenarios,
  type ScenarioInput,
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
  const { runScenario, loading: scenarioLoading } = useScenarios();

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
      <motion.div variants={fadeUp}>
        <h2 className="text-2xl font-bold gradient-text">Prediction Engine</h2>
        <p className="text-sm text-gray-500 mt-1">
          AI-powered tourism demand forecasting
          {tsData ? "" : " (using mock data)"}
        </p>
      </motion.div>

      {/* Main chart */}
      <motion.div variants={fadeUp}>
        <Panel
          title="Forecast Chart"
          subtitle="Historical arrivals + predicted values with 80%/95% confidence bands"
        >
          <ChartContainer height={380}>
            {({ width, height }) => (
              <ForecastChart
                historical={chartData.historical}
                forecast={chartData.forecast}
                width={width}
                height={height}
                yLabel="Tourist Arrivals"
              />
            )}
          </ChartContainer>
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
            </div>
          </Panel>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Panel
            title="Model Performance"
            subtitle="Forecasting model comparison"
          >
            <div className="space-y-3 py-2">
              {[
                { name: "SARIMA", mape: 5.36, active: true, best: false },
                { name: "Holt-Winters", mape: 8.87, active: false, best: false },
                { name: "Ensemble", mape: 4.12, active: true, best: true },
                { name: "Seasonal Naive", mape: 2.76, active: false, best: false },
              ].map(({ name, mape, active, best }) => (
                <div
                  key={name}
                  className="flex items-center justify-between py-2.5 px-3 rounded-lg bg-gray-800/40"
                >
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-2 h-2 rounded-full ${active ? "bg-tropical-500" : "bg-gray-600"}`}
                    />
                    <span className="text-sm text-gray-300">{name}</span>
                    {best && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-volcanic-500/20 text-volcanic-400 font-medium">
                        Best
                      </span>
                    )}
                  </div>
                  <span className="text-sm font-mono text-gray-400">
                    MAPE: {mape}%
                  </span>
                </div>
              ))}
            </div>
          </Panel>
        </motion.div>
      </div>

      {/* Heatmap */}
      <motion.div variants={fadeUp}>
        <Panel
          title="YoY Heatmap"
          subtitle="Month x Year comparison — hover any cell for details"
        >
          <ChartContainer height={280}>
            {({ width, height }) => (
              <YoYHeatmap width={width} height={height} />
            )}
          </ChartContainer>
        </Panel>
      </motion.div>
    </motion.div>
  );
}
