import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// Mock framer-motion
vi.mock("framer-motion", () => {
  const motionHandler: ProxyHandler<object> = {
    get(_target, prop) {
      return function MotionComponent({ children, ...props }: Record<string, unknown>) {
        const {
          variants: _v, initial: _i, animate: _a, whileHover: _wh,
          whileTap: _wt, exit: _e, transition: _tr, layout: _l,
          ...rest
        } = props;
        const Tag = prop as string;
        return <Tag {...rest}>{children as React.ReactNode}</Tag>;
      };
    },
  };
  return {
    motion: new Proxy({}, motionHandler),
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  };
});

// Track the model param passed to usePredictions
const mockUsePredictions = vi.fn();

vi.mock("../api/hooks", () => ({
  useTimeSeries: () => ({ data: null, error: null, refetch: vi.fn() }),
  usePredictions: (...args: unknown[]) => {
    mockUsePredictions(...args);
    return { data: null, error: null, refetch: vi.fn() };
  },
  usePredictionCompare: () => ({ data: null, loading: false, error: null, refetch: vi.fn() }),
  useScenarios: () => ({ data: null, runScenario: vi.fn(), loading: false, error: null }),
  useSavedScenarios: () => ({ data: null, refetch: vi.fn() }),
  useFeatureImportance: () => ({ data: null }),
  useTrainingInfo: () => ({ data: null }),
}));

vi.mock("../components/forecast/ForecastChart", () => ({
  __esModule: true,
  default: () => <div data-testid="forecast-chart" />,
  generateMockData: () => ({ historical: [], forecast: [] }),
}));

vi.mock("../components/forecast/ScenarioChart", () => ({
  __esModule: true,
  default: () => <div data-testid="scenario-chart" />,
  ScenarioImpactStats: () => null,
}));

vi.mock("../components/forecast/YoYHeatmap", () => ({
  __esModule: true,
  default: () => <div data-testid="yoy-heatmap" />,
}));

vi.mock("../components/shared/ChartContainer", () => ({
  __esModule: true,
  default: ({ children }: { children: (dims: { width: number; height: number }) => React.ReactNode }) =>
    <div>{children({ width: 800, height: 380 })}</div>,
}));

vi.mock("../components/shared/ErrorBoundary", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import ForecastPage from "./ForecastPage";

function renderPage(initialEntries: string[] = ["/"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <ForecastPage />
    </MemoryRouter>
  );
}

describe("ForecastPage URL state persistence", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("defaults to ensemble model when no URL param is set", () => {
    renderPage();
    expect(mockUsePredictions).toHaveBeenCalledWith("turistas", "ES709", 12, "ensemble");
  });

  it("reads model from URL params", () => {
    renderPage(["/forecast?model=sarima"]);
    expect(mockUsePredictions).toHaveBeenCalledWith("turistas", "ES709", 12, "sarima");
  });

  it("renders model list as clickable buttons with aria-pressed", () => {
    renderPage();
    // The fallback model list contains "Ensemble", "SARIMA", etc.
    const buttons = screen.getAllByRole("button", { pressed: true });
    // At least one model should be marked as active (ensemble by default)
    expect(buttons.length).toBeGreaterThanOrEqual(1);
  });

  it("changes model when a model button is clicked", () => {
    renderPage();
    // Click the SARIMA model button
    const sarimaButton = screen.getByRole("button", { name: /sarima/i });
    fireEvent.click(sarimaButton);

    // usePredictions should have been called again with sarima
    const calls = mockUsePredictions.mock.calls;
    const lastCall = calls[calls.length - 1];
    expect(lastCall[3]).toBe("sarima");
  });
});
