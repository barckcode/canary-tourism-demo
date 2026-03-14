import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import {
  useDashboardKPIs,
  usePredictions,
  useProfiles,
  useTimeSeries,
  useQuery,
  useScenarios,
} from "./hooks";

// Mock the api client module
vi.mock("./client", () => ({
  api: {
    dashboard: {
      kpis: vi.fn(),
      summary: vi.fn(),
      topMarkets: vi.fn(),
      seasonalPosition: vi.fn(),
    },
    timeseries: {
      get: vi.fn(),
      indicators: vi.fn(),
      yoy: vi.fn(),
    },
    predictions: {
      get: vi.fn(),
      compare: vi.fn(),
    },
    profiles: {
      list: vi.fn(),
      detail: vi.fn(),
      nationalities: vi.fn(),
      flows: vi.fn(),
      spending: vi.fn(),
    },
    scenarios: {
      run: vi.fn(),
    },
  },
}));

import { api } from "./client";

const mockedApi = api as {
  dashboard: { [K in keyof typeof api.dashboard]: ReturnType<typeof vi.fn> };
  timeseries: { [K in keyof typeof api.timeseries]: ReturnType<typeof vi.fn> };
  predictions: {
    [K in keyof typeof api.predictions]: ReturnType<typeof vi.fn>;
  };
  profiles: { [K in keyof typeof api.profiles]: ReturnType<typeof vi.fn> };
  scenarios: { [K in keyof typeof api.scenarios]: ReturnType<typeof vi.fn> };
};

describe("useQuery", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("starts in loading state", () => {
    const fetcher = vi.fn(() => new Promise(() => {}));
    const { result } = renderHook(() => useQuery(fetcher));

    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("returns data on successful fetch", async () => {
    const mockData = { value: 42 };
    const fetcher = vi.fn(() => Promise.resolve(mockData));

    const { result } = renderHook(() => useQuery(fetcher));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual(mockData);
    expect(result.current.error).toBeNull();
  });

  it("returns error on failed fetch", async () => {
    const fetcher = vi.fn(() => Promise.reject(new Error("Network error")));

    const { result } = renderHook(() => useQuery(fetcher));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toBeNull();
    expect(result.current.error).toBe("Network error");
  });

  it("refetches data when refetch is called", async () => {
    let callCount = 0;
    const fetcher = vi.fn(() => Promise.resolve({ count: ++callCount }));

    const { result } = renderHook(() => useQuery(fetcher));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.data).toEqual({ count: 1 });

    act(() => {
      result.current.refetch();
    });

    await waitFor(() => {
      expect(result.current.data).toEqual({ count: 2 });
    });
  });
});

describe("useDashboardKPIs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches and returns KPI data", async () => {
    const mockKPIs = {
      latest_arrivals: 500000,
      latest_period: "2025-12",
      yoy_change: 3.5,
      occupancy_rate: 72.5,
      adr: 85.0,
      revpar: 62.0,
      avg_stay: 7.2,
      last_updated: "2025-12-15",
    };

    mockedApi.dashboard.kpis.mockResolvedValueOnce(mockKPIs);

    const { result } = renderHook(() => useDashboardKPIs());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual(mockKPIs);
    expect(result.current.error).toBeNull();
    expect(mockedApi.dashboard.kpis).toHaveBeenCalledTimes(1);
  });

  it("handles API errors gracefully", async () => {
    mockedApi.dashboard.kpis.mockRejectedValueOnce(
      new Error("API error: 500 Internal Server Error")
    );

    const { result } = renderHook(() => useDashboardKPIs());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toBeNull();
    expect(result.current.error).toBe(
      "API error: 500 Internal Server Error"
    );
  });
});

describe("useTimeSeries", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches time series data with default parameters", async () => {
    const mockData = {
      data: [
        { period: "2025-01", value: 350000 },
        { period: "2025-02", value: 380000 },
      ],
      metadata: {
        indicator: "turistas",
        geo: "ES709",
        measure: "ABSOLUTE",
        total_points: 2,
      },
    };

    mockedApi.timeseries.get.mockResolvedValueOnce(mockData);

    const { result } = renderHook(() => useTimeSeries("turistas"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual(mockData);
    expect(mockedApi.timeseries.get).toHaveBeenCalledWith({
      indicator: "turistas",
      geo: "ES709",
    });
  });

  it("passes date range parameters when provided", async () => {
    mockedApi.timeseries.get.mockResolvedValueOnce({
      data: [],
      metadata: {
        indicator: "turistas",
        geo: "ES709",
        measure: "ABSOLUTE",
        total_points: 0,
      },
    });

    renderHook(() =>
      useTimeSeries("turistas", "ES709", "2024-01", "2024-12")
    );

    await waitFor(() => {
      expect(mockedApi.timeseries.get).toHaveBeenCalledWith({
        indicator: "turistas",
        geo: "ES709",
        from: "2024-01",
        to: "2024-12",
      });
    });
  });

  it("handles empty results", async () => {
    mockedApi.timeseries.get.mockResolvedValueOnce({
      data: [],
      metadata: {
        indicator: "nonexistent",
        geo: "ES709",
        measure: "ABSOLUTE",
        total_points: 0,
      },
    });

    const { result } = renderHook(() => useTimeSeries("nonexistent"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data?.data).toEqual([]);
    expect(result.current.data?.metadata.total_points).toBe(0);
  });
});

describe("usePredictions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches predictions with default parameters", async () => {
    const mockPrediction = {
      forecast: [
        {
          period: "2026-01",
          value: 460000,
          ci_lower_80: 423200,
          ci_upper_80: 496800,
          ci_lower_95: 391000,
          ci_upper_95: 529000,
        },
      ],
      model_info: {
        name: "ensemble",
        total_periods: 1,
        metrics: { rmse: 25000, mae: 18000, mape: 5.2, test_size: 12 },
      },
    };

    mockedApi.predictions.get.mockResolvedValueOnce(mockPrediction);

    const { result } = renderHook(() => usePredictions());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual(mockPrediction);
    expect(mockedApi.predictions.get).toHaveBeenCalledWith({
      indicator: "turistas",
      geo: "ES709",
      horizon: "12",
      model: "ensemble",
    });
  });

  it("passes custom parameters correctly", async () => {
    mockedApi.predictions.get.mockResolvedValueOnce({
      forecast: [],
      model_info: { name: "sarima", total_periods: 0, metrics: null },
    });

    renderHook(() => usePredictions("turistas", "ES709", 6, "sarima"));

    await waitFor(() => {
      expect(mockedApi.predictions.get).toHaveBeenCalledWith({
        indicator: "turistas",
        geo: "ES709",
        horizon: "6",
        model: "sarima",
      });
    });
  });

  it("handles prediction API errors", async () => {
    mockedApi.predictions.get.mockRejectedValueOnce(
      new Error("API error: 422 Unprocessable Entity")
    );

    const { result } = renderHook(() =>
      usePredictions("turistas", "ES709", 100)
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toBeNull();
    expect(result.current.error).toBe(
      "API error: 422 Unprocessable Entity"
    );
  });
});

describe("useProfiles", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches profile clusters", async () => {
    const mockProfiles = {
      clusters: [
        {
          id: 0,
          name: "Budget Travelers",
          size_pct: 35,
          avg_age: 32,
          avg_spend: 850,
          avg_nights: 7,
          top_nationalities: [{ nationality: "UK", percentage: 30 }],
          top_accommodations: [{ type: "3-Star Hotel", percentage: 40 }],
          top_activities: ["Beach", "Hiking"],
          top_motivations: ["Relaxation"],
          avg_satisfaction: 7.5,
          spending_breakdown: { accommodation: 40, food: 25 },
        },
      ],
    };

    mockedApi.profiles.list.mockResolvedValueOnce(mockProfiles);

    const { result } = renderHook(() => useProfiles());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual(mockProfiles);
    expect(result.current.data?.clusters).toHaveLength(1);
    expect(result.current.data?.clusters[0].name).toBe("Budget Travelers");
    expect(mockedApi.profiles.list).toHaveBeenCalledTimes(1);
  });

  it("handles empty cluster list", async () => {
    mockedApi.profiles.list.mockResolvedValueOnce({ clusters: [] });

    const { result } = renderHook(() => useProfiles());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data?.clusters).toEqual([]);
  });
});

describe("useScenarios", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("starts with no data and not loading", () => {
    const { result } = renderHook(() => useScenarios());

    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("runs a scenario and returns results", async () => {
    const mockResult = {
      baseline_forecast: [{ period: "2026-01", value: 450000 }],
      scenario_forecast: [{ period: "2026-01", value: 472500 }],
      impact_summary: {
        avg_baseline: 450000,
        avg_scenario: 472500,
        avg_change_pct: 5.0,
      },
    };

    mockedApi.scenarios.run.mockResolvedValueOnce(mockResult);

    const { result } = renderHook(() => useScenarios());

    await act(async () => {
      await result.current.runScenario({
        occupancy_change_pct: 5,
        adr_change_pct: 0,
        foreign_ratio_change_pct: 0,
        horizon: 6,
      });
    });

    expect(result.current.data).toEqual(mockResult);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("handles scenario errors", async () => {
    mockedApi.scenarios.run.mockRejectedValueOnce(
      new Error("Scenario engine failed")
    );

    const { result } = renderHook(() => useScenarios());

    await act(async () => {
      await result.current.runScenario({
        occupancy_change_pct: 100,
        adr_change_pct: 0,
        foreign_ratio_change_pct: 0,
      });
    });

    expect(result.current.data).toBeNull();
    expect(result.current.error).toBe("Scenario engine failed");
  });
});
