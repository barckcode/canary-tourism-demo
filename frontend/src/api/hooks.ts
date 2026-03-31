import { useEffect, useState, useCallback, useRef } from "react";
import { api } from "./client";

interface UseQueryResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useQuery<T>(
  fetcher: (() => Promise<T>) | null,
  deps: unknown[] = []
): UseQueryResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(fetcher !== null);
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

    // Skip fetch when fetcher is null (e.g. missing required params)
    if (!fetcher) {
      setData(null);
      setLoading(false);
      setError(null);
      return () => {};
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
  latest_arrivals: number | null;
  latest_period: string | null;
  yoy_change: number | null;
  occupancy_rate: number | null;
  adr: number | null;
  revpar: number | null;
  avg_stay: number | null;
  daily_spend: number | null;
  daily_spend_yoy: number | null;
  avg_stay_ine: number | null;
  avg_stay_ine_yoy: number | null;
  employment_total: number | null;
  employment_total_yoy: number | null;
  employment_services: number | null;
  employment_services_yoy: number | null;
  iph_index: number | null;
  iph_variation: number | null;
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

// ── Map Data ──

export interface MapMunicipality {
  name: string;
  tourism_intensity: number;
  pernoctaciones?: number;
  source: "real" | "estimated";
}

export interface MapDataResponse {
  period: string;
  municipalities: Record<string, MapMunicipality>;
  data_available: boolean;
}

export function useMapData(period?: string) {
  return useQuery<MapDataResponse>(
    () => api.dashboard.mapData(period) as Promise<MapDataResponse>,
    [period]
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
    indicator ? () => api.timeseries.get(params) as Promise<TimeSeriesResponse> : null,
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

export interface NationalityTrendPoint {
  quarter: string;
  count: number;
  avg_spend: number | null;
  avg_nights: number | null;
}

export interface NationalityTrend {
  nationality: string;
  data: NationalityTrendPoint[];
}

export function useNationalityTrends() {
  return useQuery<NationalityTrend[]>(
    () => api.profiles.nationalityTrends() as Promise<NationalityTrend[]>,
    []
  );
}

// ── Province Comparison ──

export interface ProvinceDataPoint {
  period: string;
  value: number;
}

export interface ProvinceData {
  name: string;
  data: ProvinceDataPoint[];
}

export interface ProvinceComparisonResponse {
  indicator: string;
  provinces: Record<string, ProvinceData>;
}

export function useProvinceComparison(indicator: string = "pernoctaciones", periods: number = 24) {
  return useQuery<ProvinceComparisonResponse>(
    () => api.comparison.provinces(indicator, periods) as Promise<ProvinceComparisonResponse>,
    [indicator, periods]
  );
}

// ── Accommodation Type Comparison ──

export interface AccommodationTypeData {
  name: string;
  data: ProvinceDataPoint[];
}

export interface AccommodationComparisonResponse {
  indicator: string;
  types: Record<string, AccommodationTypeData>;
}

export function useAccommodationComparison(indicator: string = "pernoctaciones", periods: number = 24) {
  return useQuery<AccommodationComparisonResponse>(
    () => api.comparison.accommodationTypes(indicator, periods) as Promise<AccommodationComparisonResponse>,
    [indicator, periods]
  );
}

// ── Scenarios ──

export interface ScenarioInput {
  occupancy_change_pct: number;
  adr_change_pct: number;
  foreign_ratio_change_pct: number;
  horizon?: number;
}

export interface ScenarioForecastPoint {
  period: string;
  value: number;
  ci_lower_80?: number | null;
  ci_upper_80?: number | null;
  ci_lower_95?: number | null;
  ci_upper_95?: number | null;
}

export interface ScenarioResponse {
  baseline_forecast: ScenarioForecastPoint[];
  scenario_forecast: ScenarioForecastPoint[];
  impact_summary: Record<string, number>;
}

export function useScenarios() {
  const [data, setData] = useState<ScenarioResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  const runScenario = useCallback(async (input: ScenarioInput) => {
    const currentRequestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const result = (await api.scenarios.run(
        input as unknown as Record<string, number>
      )) as ScenarioResponse;
      // Only update state if this is still the latest request
      if (currentRequestId === requestIdRef.current) {
        setData(result);
      }
    } catch (err) {
      if (currentRequestId === requestIdRef.current) {
        setError(err instanceof Error ? err.message : "An error occurred");
      }
    } finally {
      if (currentRequestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  }, []);

  return { data, loading, error, runScenario };
}

// ── Saved Scenarios ──

export interface SavedScenarioSummary {
  id: number;
  name: string;
  occupancy_change_pct: number;
  adr_change_pct: number;
  foreign_ratio_change_pct: number;
  horizon: number;
  created_at: string;
}

export interface SavedScenarioDetail extends SavedScenarioSummary {
  result_json: ScenarioResponse;
}

export interface ScenarioCompareResponse {
  scenarios: Record<string, ScenarioResponse>;
}

export interface FeatureImportanceResponse {
  features: Record<string, number>;
}

export function useSavedScenarios() {
  const result = useQuery<SavedScenarioSummary[]>(
    () => api.scenarios.list() as Promise<SavedScenarioSummary[]>
  );
  return result;
}

export function useFeatureImportance() {
  return useQuery<FeatureImportanceResponse>(
    () => api.scenarios.featureImportance() as Promise<FeatureImportanceResponse>
  );
}

// ── Events ──

export interface TourismEvent {
  id: number;
  name: string;
  description?: string;
  category: string;
  start_date: string;
  end_date?: string;
  impact_estimate?: string;
  location?: string;
  source: string;
  created_at: string;
}

export interface EventsResponse {
  events: TourismEvent[];
}

export interface EventCategoriesResponse {
  categories: string[];
}

export function useEvents(fromDate?: string, toDate?: string, category?: string) {
  const params: Record<string, string> = {};
  if (fromDate) params.from_date = fromDate;
  if (toDate) params.to_date = toDate;
  if (category) params.category = category;
  return useQuery<EventsResponse>(
    () => api.events.list(Object.keys(params).length > 0 ? params : undefined) as Promise<EventsResponse>,
    [fromDate, toDate, category]
  );
}

export function useEventCategories() {
  return useQuery<EventCategoriesResponse>(
    () => api.events.categories() as Promise<EventCategoriesResponse>
  );
}

// ── Event Impact ──

export interface EventImpactKPI {
  indicator: string;
  period: string;
  value: number;
}

export interface EventImpactResponse {
  event_id: number;
  event_name: string;
  start_date: string;
  end_date: string;
  category: string;
  current_kpis: EventImpactKPI[];
  previous_year_kpis: EventImpactKPI[];
  yoy_changes: Record<string, number>;
}

export function useEventImpact(eventId: number | null) {
  return useQuery<EventImpactResponse>(
    eventId !== null
      ? () => api.events.impact(eventId) as Promise<EventImpactResponse>
      : null,
    [eventId]
  );
}
