"""Pydantic response models for API endpoints.

These models serve as response_model declarations on FastAPI routers,
providing automatic OpenAPI documentation and response validation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared / reusable sub-models
# ---------------------------------------------------------------------------

class PeriodValue(BaseModel):
    """A single (period, value) data point."""

    period: str
    value: float


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardKPIsResponse(BaseModel):
    """Latest KPI values for the dashboard."""

    latest_arrivals: float | None = None
    latest_period: str | None = None
    yoy_change: float | None = None
    occupancy_rate: float | None = None
    adr: float | None = None
    revpar: float | None = None
    avg_stay: float | None = None
    daily_spend: float | None = None
    daily_spend_yoy: float | None = None
    avg_stay_ine: float | None = None
    avg_stay_ine_yoy: float | None = None
    last_updated: str | None = None
    data_available: bool = True
    reason: str | None = None


class DashboardSummaryResponse(BaseModel):
    """24-month arrivals trend, 12-month occupancy trend, and forecast."""

    arrivals_trend_24m: list[PeriodValue] = Field(default_factory=list)
    occupancy_trend_12m: list[PeriodValue] = Field(default_factory=list)
    forecast: list[PeriodValue] = Field(default_factory=list)
    data_available: bool = True
    reason: str | None = None


class MarketEntry(BaseModel):
    country: str
    code: str
    pct: float
    count: int


class TopMarketsResponse(BaseModel):
    markets: list[MarketEntry] = Field(default_factory=list)
    total: int = 0
    data_available: bool = True
    reason: str | None = None


class SeasonalPositionResponse(BaseModel):
    peak_month: str | None = None
    peak_month_number: int | None = None
    current_position: str | None = None
    current_month: str | None = None
    next_3_months: str | None = None
    next_months: list[str] = Field(default_factory=list)
    monthly_averages: dict[str, float] = Field(default_factory=dict)
    data_available: bool = True
    reason: str | None = None


class MunicipalityData(BaseModel):
    """Tourism data for a single municipality."""

    name: str
    tourism_intensity: int
    pernoctaciones: float | None = None
    source: str = Field(description="'real' if from INE data, 'estimated' otherwise")


class MapDataResponse(BaseModel):
    """Municipality-level tourism intensity data for the map."""

    period: str | None = None
    municipalities: dict[str, MunicipalityData]
    data_available: bool


# ---------------------------------------------------------------------------
# Time Series
# ---------------------------------------------------------------------------

class TimeSeriesMetadata(BaseModel):
    indicator: str
    geo: str
    measure: str
    total_points: int


class TimeSeriesResponse(BaseModel):
    """Historical time series data for a single indicator."""

    data: list[PeriodValue]
    metadata: TimeSeriesMetadata


class PaginationMeta(BaseModel):
    """Pagination metadata for paginated responses."""

    total: int
    page: int
    page_size: int
    total_pages: int


class TimeSeriesPaginatedResponse(BaseModel):
    """Paginated historical time series data for a single indicator."""

    data: list[PeriodValue]
    pagination: PaginationMeta


class IndicatorInfo(BaseModel):
    id: str
    source: str
    available_from: str
    available_to: str
    total_points: int
    last_updated: str | None = None


class YoYCell(BaseModel):
    year: int
    month: int
    value: float
    yoy_change: float | None = None


class YoYMetadata(BaseModel):
    geo: str
    total_indicators: int


class YoYResponse(BaseModel):
    indicators: dict[str, list[YoYCell]]
    metadata: YoYMetadata


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------

class ForecastPoint(BaseModel):
    """Single forecast data point with confidence intervals."""

    period: str
    value: float
    ci_lower_80: float | None = None
    ci_upper_80: float | None = None
    ci_lower_95: float | None = None
    ci_upper_95: float | None = None
    ci_available: bool = True


class ModelMetrics(BaseModel):
    rmse: float | None = None
    mae: float | None = None
    mape: float | None = None
    test_size: int | None = None


class ModelInfo(BaseModel):
    name: str
    total_periods: int
    metrics: ModelMetrics | None = None


class PredictionResponse(BaseModel):
    """Forecast for a single model."""

    forecast: list[ForecastPoint]
    model_info: ModelInfo
    requested_horizon: int = Field(description="Horizon requested by the client")
    actual_horizon: int = Field(description="Number of forecast points actually returned")
    complete: bool = Field(description="True if actual_horizon >= requested_horizon")


class PredictionCompareResponse(BaseModel):
    """Comparative forecast across all models."""

    models: dict[str, list[ForecastPoint]]
    metrics: dict[str, ModelMetrics]


class RetrainResponse(BaseModel):
    """Response from the retrain endpoint."""

    retrained: bool
    reason: str | None = None
    trained_at: str | None = None
    data_up_to: str | None = None
    duration_seconds: float | None = None
    models_trained: list[str] | None = None
    last_trained_at: str | None = None


class TrainingInfoResponse(BaseModel):
    """Information about the latest model training run."""

    trained_at: str | None = None
    data_up_to: str | None = None
    status: str
    models_trained: list[str] = Field(default_factory=list)
    duration_seconds: float | None = None


class PredictionVersionEntry(BaseModel):
    """A single version of predictions for a model/indicator."""

    version: int
    trained_at: str | None = None
    is_current: bool = False
    forecast: list[ForecastPoint]


class PredictionHistoryResponse(BaseModel):
    """History of prediction versions for a model/indicator."""

    model: str
    indicator: str
    geo_code: str
    total_versions: int
    versions: list[PredictionVersionEntry]


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

class NationalityEntry(BaseModel):
    nationality: str
    percentage: float = 0


class AccommodationEntry(BaseModel):
    type: str
    percentage: float = 0


class ClusterSummary(BaseModel):
    id: int
    name: str
    size_pct: float
    avg_age: float | None = None
    avg_spend: float | None = None
    avg_nights: float | None = None
    top_nationalities: list[NationalityEntry]
    top_accommodations: list[AccommodationEntry]
    top_activities: list[str]
    top_motivations: list[str]
    avg_satisfaction: float | None = None
    spending_breakdown: dict = Field(default_factory=dict)


class ProfilesListResponse(BaseModel):
    """List of all tourist profile clusters."""

    clusters: list[ClusterSummary]


class ProfileDetailResponse(ClusterSummary):
    """Detailed profile for a single cluster."""

    characteristics: dict = Field(default_factory=dict)


class NationalityProfileEntry(BaseModel):
    nationality: str
    count: int
    avg_spend: float | None = None
    avg_nights: float | None = None


class SankeyNode(BaseModel):
    id: str
    label: str


class SankeyLink(BaseModel):
    source: str
    target: str
    value: int


class FlowsResponse(BaseModel):
    nodes: list[SankeyNode]
    links: list[SankeyLink]


class SpendingCategory(BaseModel):
    category: str
    amount: float
    pct: float


class SpendingByClusterResponse(BaseModel):
    spending_by_cluster: dict[str, list[SpendingCategory]]


class NationalityTrendPoint(BaseModel):
    """A single quarter data point for a nationality trend."""

    quarter: str
    count: int
    avg_spend: float | None = None
    avg_nights: float | None = None


class NationalityTrendResponse(BaseModel):
    """Temporal trend data for a single nationality."""

    nationality: str
    data: list[NationalityTrendPoint]


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

class ScenarioForecastPoint(BaseModel):
    period: str
    value: float


class ImpactSummary(BaseModel):
    avg_baseline: float = 0
    avg_scenario: float = 0
    avg_change_pct: float = 0


class ScenarioParams(BaseModel):
    occupancy_change_pct: float = 0
    adr_change_pct: float = 0
    foreign_ratio_change_pct: float = 0


class ScenarioResponse(BaseModel):
    baseline_forecast: list[ScenarioForecastPoint]
    scenario_forecast: list[ScenarioForecastPoint]
    impact_summary: ImpactSummary | dict = Field(default_factory=dict)
    params: ScenarioParams | dict = Field(default_factory=dict)


class SavedScenarioSummary(BaseModel):
    """Lightweight saved scenario listing (without full result)."""

    id: int
    name: str
    occupancy_change_pct: float = 0.0
    adr_change_pct: float = 0.0
    foreign_ratio_change_pct: float = 0.0
    horizon: int = 12
    created_at: str | None = None


class SavedScenarioDetail(SavedScenarioSummary):
    """Full saved scenario including the result."""

    result: ScenarioResponse


class SavedScenarioListResponse(BaseModel):
    """List of saved scenarios."""

    scenarios: list[SavedScenarioSummary]


class CompareResponse(BaseModel):
    """Comparison of multiple saved scenarios keyed by ID."""

    scenarios: dict[str, SavedScenarioDetail]


class FeatureImportanceResponse(BaseModel):
    """GBR model feature importances."""

    importances: dict[str, float]


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class EventResponse(BaseModel):
    """A single tourism event."""

    id: int
    name: str
    description: str | None = None
    category: str
    start_date: str
    end_date: str | None = None
    impact_estimate: str | None = None
    location: str | None = None
    source: str | None = None
    created_at: str | None = None


class EventListResponse(BaseModel):
    """List of tourism events."""

    events: list[EventResponse]


class CreateEventRequest(BaseModel):
    """Request body to create a custom tourism event."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    category: str = Field(..., min_length=1, max_length=50)
    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    impact_estimate: str | None = Field(None, max_length=200)
    location: str | None = Field(None, max_length=200)


class EventKPI(BaseModel):
    """A single KPI data point for an event period."""

    indicator: str
    period: str
    value: float | None


class EventImpactResponse(BaseModel):
    """Impact analysis for a tourism event with KPI correlation."""

    event_id: int
    event_name: str
    start_date: str
    end_date: str
    category: str
    current_kpis: list[EventKPI]
    previous_year_kpis: list[EventKPI]
    yoy_changes: dict[str, float | None]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class DatabaseHealth(BaseModel):
    """Database connectivity and record counts."""

    status: str = Field(description="'ok' or 'error'")
    time_series_count: int = 0
    predictions_count: int = 0
    profiles_count: int = 0


class ForecasterHealth(BaseModel):
    """Forecaster model status."""

    status: str = Field(description="'ok' or 'not_trained'")
    last_training: str | None = None


class ProfilerHealth(BaseModel):
    """Profiler model status."""

    status: str = Field(description="'ok' or 'not_trained'")
    clusters: int = 0


class ModelsHealth(BaseModel):
    """Aggregated ML model health."""

    forecaster: ForecasterHealth
    profiler: ProfilerHealth


class ETLHealth(BaseModel):
    """ETL pipeline freshness."""

    last_success: str | None = None
    last_failure: str | None = None


class DataFreshness(BaseModel):
    """Latest data availability information."""

    latest_period: str | None = None
    days_since_update: int | None = None


class DetailedHealthResponse(BaseModel):
    """Full system health check response."""

    status: str = Field(description="'ok', 'degraded', or 'unhealthy'")
    timestamp: str
    database: DatabaseHealth
    models: ModelsHealth
    etl: ETLHealth
    data_freshness: DataFreshness


class ReadinessResponse(BaseModel):
    """Readiness probe response for orchestrators."""

    ready: bool
    reason: str | None = None
