import { useEffect, useState, useCallback, useRef } from "react";
import { api } from "./client";

interface UseQueryResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useQuery<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = []
): UseQueryResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Serialize deps to a stable string to prevent infinite loops
  // from unstable object/array references
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const depsKey = JSON.stringify(deps);

  const fetchData = useCallback(() => {
    // Cancel any in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    fetcher()
      .then((result) => {
        if (!controller.signal.aborted) {
          setData(result);
          setError(null);
        }
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : String(err));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [depsKey]);

  useEffect(() => {
    const cleanup = fetchData();
    return cleanup;
  }, [fetchData]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return { data, loading, error, refetch: fetchData };
}

// ── Dashboard ──

export interface DashboardKPIs {
  latest_arrivals: number;
  latest_period: string;
  yoy_change: number;
  occupancy_rate: number;
  adr: number;
  revpar: number;
  avg_stay: number;
  last_updated: string;
}

export function useDashboardKPIs() {
  return useQuery<DashboardKPIs>(
    () => api.dashboard.kpis() as Promise<DashboardKPIs>
  );
}

export interface DashboardSummary {
  arrivals_trend_24m: { period: string; value: number }[];
  occupancy_trend_12m: { period: string; value: number }[];
  forecast: { period: string; value: number }[];
}

export function useDashboardSummary() {
  return useQuery<DashboardSummary>(
    () => api.dashboard.summary() as Promise<DashboardSummary>
  );
}

export interface TopMarket {
  country: string;
  code: string;
  pct: number;
  count: number;
}

export interface TopMarketsResponse {
  markets: TopMarket[];
  total: number;
}

export function useTopMarkets() {
  return useQuery<TopMarketsResponse>(
    () => api.dashboard.topMarkets() as Promise<TopMarketsResponse>
  );
}

export interface SeasonalPositionResponse {
  peak_month: string;
  peak_month_number: number;
  current_position: string;
  current_month: string;
  next_3_months: string;
  next_months: string[];
  monthly_averages: Record<string, number>;
}

export function useSeasonalPosition() {
  return useQuery<SeasonalPositionResponse>(
    () => api.dashboard.seasonalPosition() as Promise<SeasonalPositionResponse>
  );
}

// ── Time Series ──

export interface TimeSeriesPoint {
  period: string;
  value: number;
}

export interface TimeSeriesResponse {
  data: TimeSeriesPoint[];
  metadata: {
    indicator: string;
    geo: string;
    measure: string;
    total_points: number;
  };
}

export function useTimeSeries(
  indicator: string,
  geo = "ES709",
  from?: string,
  to?: string
) {
  const params: Record<string, string> = { indicator, geo };
  if (from) params.from = from;
  if (to) params.to = to;
  return useQuery<TimeSeriesResponse>(
    () => api.timeseries.get(params) as Promise<TimeSeriesResponse>,
    [indicator, geo, from, to]
  );
}

export interface IndicatorInfo {
  id: string;
  source: string;
  available_from: string;
  available_to: string;
  total_points: number;
}

export function useIndicators() {
  return useQuery<IndicatorInfo[]>(
    () => api.timeseries.indicators() as Promise<IndicatorInfo[]>
  );
}

// ── YoY Heatmap ──

export interface YoYCell {
  year: number;
  month: number;
  value: number;
  yoy_change: number | null;
}

export interface YoYResponse {
  indicators: Record<string, YoYCell[]>;
  metadata: {
    geo: string;
    total_indicators: number;
  };
}

export function useYoYHeatmap(indicator?: string, geo = "ES709") {
  const params: Record<string, string> = { geo };
  if (indicator) params.indicator = indicator;
  return useQuery<YoYResponse>(
    () => api.timeseries.yoy(params) as Promise<YoYResponse>,
    [indicator, geo]
  );
}

// ── Predictions ──

export interface ForecastPoint {
  period: string;
  value: number;
  ci_lower_80: number;
  ci_upper_80: number;
  ci_lower_95: number;
  ci_upper_95: number;
}

export interface ModelAccuracyMetrics {
  rmse: number;
  mae: number;
  mape: number;
  test_size: number;
}

export interface PredictionResponse {
  forecast: ForecastPoint[];
  model_info: {
    name: string;
    total_periods: number;
    metrics: ModelAccuracyMetrics | null;
  };
}

export function usePredictions(
  indicator = "turistas",
  geo = "ES709",
  horizon = 12,
  model = "ensemble"
) {
  return useQuery<PredictionResponse>(
    () =>
      api.predictions.get({
        indicator,
        geo,
        horizon: String(horizon),
        model,
      }) as Promise<PredictionResponse>,
    [indicator, geo, horizon, model]
  );
}

export interface PredictionCompareResponse {
  models: Record<string, ForecastPoint[]>;
  metrics?: Record<string, ModelAccuracyMetrics>;
}

export function usePredictionCompare(
  indicator = "turistas",
  geo = "ES709",
  horizon = 12
) {
  return useQuery<PredictionCompareResponse>(
    () =>
      api.predictions.compare({
        indicator,
        geo,
        horizon: String(horizon),
      }) as Promise<PredictionCompareResponse>,
    [indicator, geo, horizon]
  );
}

// ── Training Info ──

export interface TrainingInfo {
  last_trained_at: string;
  data_up_to: string;
  status: string;
  models_trained: string[];
  duration_seconds: number;
}

export function useTrainingInfo() {
  return useQuery<TrainingInfo>(
    () => api.predictions.trainingInfo() as Promise<TrainingInfo>
  );
}

// ── Profiles ──

export interface NationalityEntry {
  nationality: string;
  percentage: number;
}

export interface AccommodationEntry {
  type: string;
  percentage: number;
}

export interface ActivityEntry {
  activity: string;
  percentage: number;
}

export interface MotivationEntry {
  motivation: string;
  percentage: number;
}

export interface SpendingCategory {
  category: string;
  amount: number;
  pct: number;
}

export interface ClusterProfile {
  id: number;
  name: string;
  size_pct: number;
  avg_age: number;
  avg_spend: number;
  avg_nights: number;
  top_nationalities: NationalityEntry[];
  top_accommodations: AccommodationEntry[];
  top_activities: string[];
  top_motivations: string[];
  avg_satisfaction: number | null;
  spending_breakdown: Record<string, number>;
}

export interface ClusterDetail extends ClusterProfile {
  characteristics: Record<string, unknown>;
}

export interface ProfilesResponse {
  clusters: ClusterProfile[];
}

export function useProfiles() {
  return useQuery<ProfilesResponse>(
    () => api.profiles.list() as Promise<ProfilesResponse>
  );
}

export function useProfileDetail(clusterId: number | null) {
  return useQuery<ClusterDetail | null>(
    () =>
      clusterId !== null
        ? (api.profiles.detail(clusterId) as Promise<ClusterDetail>)
        : Promise.resolve(null),
    [clusterId]
  );
}

export interface NationalityProfile {
  nationality: string;
  count: number;
  avg_spend: number;
  avg_nights: number;
}

export function useNationalityProfiles() {
  return useQuery<NationalityProfile[]>(
    () => api.profiles.nationalities() as Promise<NationalityProfile[]>
  );
}

export interface FlowData {
  nodes: { id: string; label: string }[];
  links: { source: string; target: string; value: number }[];
}

export function useFlowData() {
  return useQuery<FlowData>(
    () => api.profiles.flows() as Promise<FlowData>
  );
}

export interface SpendingByClusterResponse {
  spending_by_cluster: Record<string, SpendingCategory[]>;
}

export function useSpendingByCluster() {
  return useQuery<SpendingByClusterResponse>(
    () => api.profiles.spending() as Promise<SpendingByClusterResponse>
  );
}

// ── Scenarios ──

export interface ScenarioInput {
  occupancy_change_pct: number;
  adr_change_pct: number;
  foreign_ratio_change_pct: number;
  horizon?: number;
}

export interface ScenarioResponse {
  baseline_forecast: ForecastPoint[];
  scenario_forecast: ForecastPoint[];
  impact_summary: Record<string, number>;
}

export function useScenarios() {
  const [data, setData] = useState<ScenarioResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runScenario = useCallback(async (input: ScenarioInput) => {
    setLoading(true);
    setError(null);
    try {
      const result = (await api.scenarios.run(
        input as unknown as Record<string, number>
      )) as ScenarioResponse;
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  }, []);

  return { data, loading, error, runScenario };
}
