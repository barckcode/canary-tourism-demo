import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// Mock framer-motion to avoid animation issues in tests
vi.mock("framer-motion", () => {
  const motionHandler: ProxyHandler<object> = {
    get(_target, prop) {
      // Return a simple component for any motion.* element
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

// Mock the API hooks
const mockUseIndicators = vi.fn();
const mockUseTimeSeries = vi.fn();
const mockUseProvinceComparison = vi.fn();

vi.mock("../api/hooks", () => ({
  useIndicators: () => mockUseIndicators(),
  useTimeSeries: (indicator: string) => mockUseTimeSeries(indicator),
  useProvinceComparison: (...args: unknown[]) => mockUseProvinceComparison(...args),
}));

// Mock chart components since they use D3 which doesn't work well in jsdom
vi.mock("../components/forecast/ForecastChart", () => ({
  __esModule: true,
  default: ({ yLabel }: { yLabel?: string }) => (
    <div data-testid="forecast-chart">{yLabel}</div>
  ),
}));

vi.mock("../components/shared/ComparisonChart", () => ({
  __esModule: true,
  default: ({ series }: { series: { name: string }[] }) => (
    <div data-testid="comparison-chart">
      {series.map((s) => s.name).join(", ")}
    </div>
  ),
}));

vi.mock("../components/shared/ChartContainer", () => ({
  __esModule: true,
  default: ({ children }: { children: (dims: { width: number; height: number }) => React.ReactNode }) =>
    <div>{children({ width: 800, height: 360 })}</div>,
}));

import DataExplorerPage from "./DataExplorerPage";

function renderPage(initialEntries: string[] = ["/"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <DataExplorerPage />
    </MemoryRouter>
  );
}

const fakeIndicators = [
  { id: "turistas", source: "istac", available_from: "2010-01", available_to: "2026-01", total_points: 193 },
  { id: "ocupacion", source: "istac", available_from: "2009-01", available_to: "2026-01", total_points: 205 },
  { id: "adr", source: "istac", available_from: "2009-01", available_to: "2026-01", total_points: 205 },
  { id: "revpar", source: "istac", available_from: "2009-01", available_to: "2026-01", total_points: 205 },
];

const fakeTimeSeriesResponse = (indicator: string) => ({
  data: {
    data: [
      { period: "2025-01", value: 100 },
      { period: "2025-02", value: 200 },
    ],
    metadata: { indicator, geo: "ES709", measure: "absolute", total_points: 2 },
  },
  loading: false,
  error: null,
  refetch: vi.fn(),
});

const emptyTsResponse = {
  data: null,
  loading: false,
  error: null,
  refetch: vi.fn(),
};

describe("DataExplorerPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseIndicators.mockReturnValue({
      data: fakeIndicators,
      error: null,
      refetch: vi.fn(),
    });
    mockUseTimeSeries.mockImplementation((indicator: string) => {
      if (!indicator) return emptyTsResponse;
      return fakeTimeSeriesResponse(indicator);
    });
    mockUseProvinceComparison.mockReturnValue({
      data: {
        indicator: "pernoctaciones",
        provinces: {
          ES709: {
            name: "Santa Cruz de Tenerife",
            data: [
              { period: "2025-02", value: 1345678 },
              { period: "2025-01", value: 1234567 },
              { period: "2024-02", value: 1200000 },
              { period: "2024-01", value: 1100000 },
            ],
          },
          ES701: {
            name: "Las Palmas",
            data: [
              { period: "2025-02", value: 3567890 },
              { period: "2025-01", value: 3456789 },
              { period: "2024-02", value: 3400000 },
              { period: "2024-01", value: 3300000 },
            ],
          },
        },
      },
      loading: false,
      error: null,
      refetch: vi.fn(),
    });
  });

  it("renders the indicator table", () => {
    renderPage();
    expect(screen.getByText("turistas")).toBeInTheDocument();
    expect(screen.getByText("ocupacion")).toBeInTheDocument();
    expect(screen.getByText("adr")).toBeInTheDocument();
  });

  it("renders View buttons for all indicators", () => {
    renderPage();
    const viewButtons = screen.getAllByRole("button", { name: /view/i });
    expect(viewButtons.length).toBe(fakeIndicators.length);
  });

  it("selects a single indicator and shows the chart", () => {
    renderPage();
    const viewButton = screen.getByRole("button", { name: /view turistas/i });
    fireEvent.click(viewButton);

    expect(screen.getByTestId("forecast-chart")).toBeInTheDocument();
  });

  it("selects multiple indicators and shows comparison chart", () => {
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /view turistas/i }));
    fireEvent.click(screen.getByRole("button", { name: /view ocupacion/i }));

    expect(screen.getByTestId("comparison-chart")).toBeInTheDocument();
    expect(screen.getByTestId("comparison-chart").textContent).toContain("turistas");
    expect(screen.getByTestId("comparison-chart").textContent).toContain("ocupacion");
  });

  it("limits selection to 3 indicators", () => {
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /view turistas/i }));
    fireEvent.click(screen.getByRole("button", { name: /view ocupacion/i }));
    fireEvent.click(screen.getByRole("button", { name: /view adr/i }));

    // Fourth indicator button should be disabled
    const revparButton = screen.getByRole("button", { name: /view revpar/i });
    expect(revparButton).toBeDisabled();
  });

  it("shows max indicators message when 3 are selected", () => {
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /view turistas/i }));
    fireEvent.click(screen.getByRole("button", { name: /view ocupacion/i }));
    fireEvent.click(screen.getByRole("button", { name: /view adr/i }));

    expect(screen.getByText("Max 3 indicators")).toBeInTheDocument();
  });

  it("deselects an indicator when clicking its button again", () => {
    renderPage();

    const viewButton = screen.getByRole("button", { name: /view turistas/i });
    fireEvent.click(viewButton);
    expect(screen.getByTestId("forecast-chart")).toBeInTheDocument();

    // Click the same button (now "Selected") to deselect
    const selectedButton = screen.getByRole("button", { name: /deselect turistas/i });
    fireEvent.click(selectedButton);

    expect(screen.queryByTestId("forecast-chart")).not.toBeInTheDocument();
  });

  it("shows clear selection button when indicators are selected", () => {
    renderPage();

    expect(screen.queryByRole("button", { name: /clear selection/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /view turistas/i }));
    expect(screen.getByRole("button", { name: /clear selection/i })).toBeInTheDocument();
  });

  it("clears all selections when clear button is clicked", () => {
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /view turistas/i }));
    fireEvent.click(screen.getByRole("button", { name: /view ocupacion/i }));

    const clearButton = screen.getByRole("button", { name: /clear selection/i });
    fireEvent.click(clearButton);

    expect(screen.queryByTestId("forecast-chart")).not.toBeInTheDocument();
    expect(screen.queryByTestId("comparison-chart")).not.toBeInTheDocument();
  });

  it("shows selection count badge", () => {
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /view turistas/i }));
    // The badge renders "{count} selected" -- may appear in badge + panel subtitle
    const badges1 = screen.getAllByText(/1 selected/);
    expect(badges1.length).toBeGreaterThanOrEqual(1);

    fireEvent.click(screen.getByRole("button", { name: /view ocupacion/i }));
    const badges2 = screen.getAllByText(/2 selected/);
    expect(badges2.length).toBeGreaterThanOrEqual(1);
  });

  it("uses aria-pressed attribute to reflect selection state", () => {
    renderPage();

    const button = screen.getByRole("button", { name: /view turistas/i });
    expect(button).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(button);

    const selectedButton = screen.getByRole("button", { name: /deselect turistas/i });
    expect(selectedButton).toHaveAttribute("aria-pressed", "true");
  });

  it("restores selected indicator from URL params", () => {
    renderPage(["/data-explorer?indicator=turistas"]);
    // The indicator should be pre-selected, so chart should be visible
    expect(screen.getByTestId("forecast-chart")).toBeInTheDocument();
  });

  it("restores multiple indicators from URL params", () => {
    renderPage(["/data-explorer?indicator=turistas,ocupacion"]);
    expect(screen.getByTestId("comparison-chart")).toBeInTheDocument();
  });
});
