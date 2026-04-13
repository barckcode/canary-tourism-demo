import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

// Mock framer-motion to avoid animation issues in tests
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

// Mock the API hooks
const mockUseDashboardKPIs = vi.fn();
const mockUseDashboardSummary = vi.fn();
const mockUseTopMarkets = vi.fn();
const mockUseSeasonalPosition = vi.fn();

vi.mock("../api/hooks", () => ({
  useDashboardKPIs: () => mockUseDashboardKPIs(),
  useDashboardSummary: () => mockUseDashboardSummary(),
  useTopMarkets: () => mockUseTopMarkets(),
  useSeasonalPosition: () => mockUseSeasonalPosition(),
}));

// Mock heavy sub-components to avoid D3/WebGL dependencies
vi.mock("../components/map/TenerifeMap", () => ({
  __esModule: true,
  default: ({ period }: { period: string }) => (
    <div data-testid="tenerife-map">Map: {period}</div>
  ),
}));

vi.mock("../components/shared/SparklineChart", () => ({
  __esModule: true,
  default: () => <div data-testid="sparkline-chart">Sparkline</div>,
}));

vi.mock("../components/shared/ErrorBoundary", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("../components/timeline/TimeSlider", () => ({
  __esModule: true,
  default: ({ onChange }: { onChange: (p: string) => void; startYear: number; endYear: number }) => (
    <div data-testid="time-slider">
      <button onClick={() => onChange("2025-06")}>Change Period</button>
    </div>
  ),
}));

vi.mock("../components/shared/AnimatedNumber", () => ({
  __esModule: true,
  default: ({ value, format }: { value: number; format: (n: number) => string }) => (
    <span data-testid="animated-number">{format(value)}</span>
  ),
}));

vi.mock("../components/shared/ExportCSVButton", () => ({
  __esModule: true,
  default: () => <button data-testid="export-csv">Export</button>,
}));

import DashboardPage from "./DashboardPage";
import type { DashboardKPIs } from "../api/hooks";

const fakeKpis: DashboardKPIs = {
  latest_arrivals: 450000,
  latest_period: "2025-03",
  yoy_change: 5.2,
  occupancy_rate: 78.3,
  adr: 112,
  revpar: 87.7,
  avg_stay: 7.2,
  daily_spend: 145,
  daily_spend_yoy: 3.1,
  avg_stay_ine: 4.5,
  avg_stay_ine_yoy: -0.8,
  employment_total: 124.5,
  employment_total_yoy: 2.3,
  employment_services: 98.2,
  employment_services_yoy: 1.8,
  iph_index: 105.3,
  iph_variation: 3.5,
  last_updated: "2025-03-15",
};

const fakeSummary = {
  arrivals_trend_24m: [
    { period: "2024-01", value: 400000 },
    { period: "2024-02", value: 420000 },
  ],
  occupancy_trend_12m: [{ period: "2024-01", value: 75 }],
  forecast: [{ period: "2025-04", value: 460000 }],
};

const fakeTopMarkets = {
  markets: [
    { country: "United Kingdom", code: "GB", pct: 35, count: 157500 },
    { country: "Germany", code: "DE", pct: 25, count: 112500 },
    { country: "Spain", code: "ES", pct: 15, count: 67500 },
  ],
  total: 450000,
};

const fakeSeasonal = {
  peak_month: "January",
  peak_month_number: 1,
  current_position: "High",
  current_month: "March",
  next_3_months: "Medium",
  next_months: ["April", "May", "June"],
  monthly_averages: { "1": 500000, "2": 480000 },
};

function defaultHookState() {
  mockUseDashboardKPIs.mockReturnValue({
    data: fakeKpis,
    loading: false,
    error: null,
    refetch: vi.fn(),
  });
  mockUseDashboardSummary.mockReturnValue({
    data: fakeSummary,
    loading: false,
    error: null,
    refetch: vi.fn(),
  });
  mockUseTopMarkets.mockReturnValue({
    data: fakeTopMarkets,
    loading: false,
    error: null,
    refetch: vi.fn(),
  });
  mockUseSeasonalPosition.mockReturnValue({
    data: fakeSeasonal,
    loading: false,
    error: null,
    refetch: vi.fn(),
  });
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    defaultHookState();
  });

  it("renders the page title and subtitle", () => {
    render(<DashboardPage />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Tenerife tourism overview")).toBeInTheDocument();
  });

  it("renders KPI cards with formatted values when data loads", async () => {
    render(<DashboardPage />);

    // Arrivals: 450000 -> "450K"
    await waitFor(() => {
      expect(screen.getByText("450K")).toBeInTheDocument();
    });
    // YoY Change: 5.2 -> "+5.2%"
    expect(screen.getByText("+5.2%")).toBeInTheDocument();
    // Occupancy: 78.3 -> "78.3%"
    expect(screen.getByText("78.3%")).toBeInTheDocument();
    // ADR: 112 -> "€112"
    expect(screen.getByText("€112")).toBeInTheDocument();
    // Avg Stay: 7.2 -> "7.2n"
    expect(screen.getByText("7.2n")).toBeInTheDocument();
    // Daily Spend: 145 -> "145 €"
    expect(screen.getByText("145 €")).toBeInTheDocument();
    // Avg Stay INE: 4.5 -> "4.5d"
    expect(screen.getByText("4.5d")).toBeInTheDocument();
  });

  it("renders KPI labels from translations", () => {
    render(<DashboardPage />);
    expect(screen.getByText("Arrivals")).toBeInTheDocument();
    expect(screen.getByText("YoY Change")).toBeInTheDocument();
    expect(screen.getByText("Occupancy")).toBeInTheDocument();
    expect(screen.getByText("ADR")).toBeInTheDocument();
    expect(screen.getByText("RevPAR")).toBeInTheDocument();
    expect(screen.getByText("Avg Stay")).toBeInTheDocument();
    expect(screen.getByText("Avg. Daily Spend")).toBeInTheDocument();
    expect(screen.getByText("Hotel Price Index")).toBeInTheDocument();
  });

  it("shows loading skeleton when KPIs are loading", () => {
    mockUseDashboardKPIs.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: vi.fn(),
    });
    const { container } = render(<DashboardPage />);
    const pulseElements = container.querySelectorAll(".animate-pulse");
    expect(pulseElements.length).toBeGreaterThan(0);
  });

  it("shows error state when KPI API fails", () => {
    mockUseDashboardKPIs.mockReturnValue({
      data: null,
      loading: false,
      error: "Server error",
      refetch: vi.fn(),
    });
    render(<DashboardPage />);
    expect(screen.getByText("Could not load KPI data.")).toBeInTheDocument();
  });

  it("shows error state when trend API fails", () => {
    mockUseDashboardSummary.mockReturnValue({
      data: null,
      loading: false,
      error: "Server error",
      refetch: vi.fn(),
    });
    render(<DashboardPage />);
    expect(screen.getByText("Could not load trend data.")).toBeInTheDocument();
  });

  it("shows error state when markets API fails", () => {
    mockUseTopMarkets.mockReturnValue({
      data: null,
      loading: false,
      error: "Server error",
      refetch: vi.fn(),
    });
    render(<DashboardPage />);
    expect(screen.getByText("Could not load market data.")).toBeInTheDocument();
  });

  it("shows error state when seasonal API fails", () => {
    mockUseSeasonalPosition.mockReturnValue({
      data: null,
      loading: false,
      error: "Server error",
      refetch: vi.fn(),
    });
    render(<DashboardPage />);
    expect(screen.getByText("Could not load seasonal data.")).toBeInTheDocument();
  });

  it("displays data freshness indicator with latest period", () => {
    render(<DashboardPage />);
    expect(screen.getByText(/Data as of:.*2025-03/)).toBeInTheDocument();
  });

  it("displays last updated timestamp", () => {
    render(<DashboardPage />);
    expect(screen.getByText(/2025-03-15/)).toBeInTheDocument();
  });

  it("renders the sparkline chart when summary data is available", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("sparkline-chart")).toBeInTheDocument();
  });

  it("renders top markets with country names and percentages", () => {
    render(<DashboardPage />);
    expect(screen.getByText("United Kingdom")).toBeInTheDocument();
    expect(screen.getByText("Germany")).toBeInTheDocument();
    expect(screen.getByText("Spain")).toBeInTheDocument();
    expect(screen.getByText("35%")).toBeInTheDocument();
    expect(screen.getByText("25%")).toBeInTheDocument();
    expect(screen.getByText("15%")).toBeInTheDocument();
  });

  it("renders market share progress bars with correct ARIA attributes", () => {
    render(<DashboardPage />);
    const progressBars = screen.getAllByRole("progressbar");
    expect(progressBars.length).toBe(3);
    expect(progressBars[0]).toHaveAttribute("aria-valuenow", "35");
    expect(progressBars[0]).toHaveAttribute("aria-valuemin", "0");
    expect(progressBars[0]).toHaveAttribute("aria-valuemax", "100");
  });

  it("renders seasonal position data", () => {
    render(<DashboardPage />);
    expect(screen.getByText("Peak Month")).toBeInTheDocument();
    expect(screen.getByText("January")).toBeInTheDocument();
    expect(screen.getByText("Current")).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByText("Next 3 months")).toBeInTheDocument();
    expect(screen.getByText("Medium")).toBeInTheDocument();
  });

  it("renders the TenerifeMap component", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("tenerife-map")).toBeInTheDocument();
  });

  it("renders the TimeSlider component", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("time-slider")).toBeInTheDocument();
  });

  it("renders the export CSV button", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("export-csv")).toBeInTheDocument();
  });

  it("shows YoY indicators for KPIs that have yoyKey", () => {
    render(<DashboardPage />);
    // employment_total_yoy = 2.3 -> "▲ +2.3% YoY"
    expect(screen.getByText(/\+2\.3% YoY/)).toBeInTheDocument();
    // employment_services_yoy = 1.8 -> "▲ +1.8% YoY"
    expect(screen.getByText(/\+1\.8% YoY/)).toBeInTheDocument();
    // iph_variation = 3.5 -> "▲ +3.5% YoY"
    expect(screen.getByText(/\+3\.5% YoY/)).toBeInTheDocument();
  });

  it("shows loading skeletons for markets when markets are loading", () => {
    mockUseTopMarkets.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: vi.fn(),
    });
    const { container } = render(<DashboardPage />);
    // Markets section should have aria-busy=true
    const marketsSection = container.querySelector("[aria-busy='true']");
    expect(marketsSection).toBeInTheDocument();
  });

  it("shows em-dash for KPI values that are null", () => {
    mockUseDashboardKPIs.mockReturnValue({
      data: {
        ...fakeKpis,
        latest_arrivals: null,
        yoy_change: null,
      },
      loading: false,
      error: null,
      refetch: vi.fn(),
    });
    render(<DashboardPage />);
    // null values should show "—"
    const emDashes = screen.getAllByText("\u2014");
    expect(emDashes.length).toBeGreaterThanOrEqual(2);
  });

  it("sets aria-busy on KPI grid while loading", () => {
    mockUseDashboardKPIs.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: vi.fn(),
    });
    const { container } = render(<DashboardPage />);
    const busyGrid = container.querySelector("[aria-busy='true']");
    expect(busyGrid).toBeInTheDocument();
  });

  it("does not show data freshness when latest_period is null", () => {
    mockUseDashboardKPIs.mockReturnValue({
      data: { ...fakeKpis, latest_period: null },
      loading: false,
      error: null,
      refetch: vi.fn(),
    });
    render(<DashboardPage />);
    expect(screen.queryByText(/Data as of/)).not.toBeInTheDocument();
  });
});
