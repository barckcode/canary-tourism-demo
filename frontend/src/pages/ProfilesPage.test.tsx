import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
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

const mockUseProfileDetail = vi.fn();
let mockTrendsReturn = { data: null as typeof fakeTrendsData | null, error: null, loading: false, refetch: vi.fn() };

const fakeClusters = [
  {
    id: 0, name: "Budget Travelers", size_pct: 35, avg_age: 32, avg_spend: 800,
    avg_nights: 5.2, avg_satisfaction: 7.5,
    top_nationalities: [{ nationality: "German", count: 100 }],
    top_accommodations: [{ type: "Hotel" }],
    top_activities: ["Beach"],
    top_motivations: ["Relaxation"],
  },
  {
    id: 1, name: "Premium Visitors", size_pct: 25, avg_age: 45, avg_spend: 2000,
    avg_nights: 7.1, avg_satisfaction: 8.2,
    top_nationalities: [{ nationality: "British", count: 80 }],
    top_accommodations: [{ type: "Resort" }],
    top_activities: ["Golf"],
    top_motivations: ["Luxury"],
  },
];

vi.mock("../api/hooks", () => ({
  useProfiles: () => ({ data: { clusters: fakeClusters }, error: null, refetch: vi.fn() }),
  useProfileDetail: (...args: unknown[]) => {
    mockUseProfileDetail(...args);
    return { data: null };
  },
  useNationalityProfiles: () => ({ data: null, error: null, refetch: vi.fn() }),
  useFlowData: () => ({ data: null, error: null, refetch: vi.fn() }),
  useSpendingByCluster: () => ({ data: null }),
  useNationalityTrends: () => mockTrendsReturn,
}));

vi.mock("../components/profiles/ClusterViz", () => ({
  __esModule: true,
  default: ({ onSelect, clusters }: { onSelect: (c: unknown) => void; clusters?: unknown[] }) => (
    <div data-testid="cluster-viz">
      {clusters?.map((c: Record<string, unknown>, i: number) => (
        <button key={i} onClick={() => onSelect(c)} data-testid={`cluster-${c.id}`}>
          {String(c.name)}
        </button>
      ))}
    </div>
  ),
}));

vi.mock("../components/profiles/SankeyFlow", () => ({
  __esModule: true,
  default: () => <div data-testid="sankey-flow" />,
}));

vi.mock("../components/shared/ChartContainer", () => ({
  __esModule: true,
  default: ({ children }: { children: (dims: { width: number; height: number }) => React.ReactNode }) =>
    <div>{children({ width: 800, height: 320 })}</div>,
}));

vi.mock("../components/shared/ErrorBoundary", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const fakeTrendsData = [
  {
    nationality: "United Kingdom",
    data: [
      { quarter: "2023-Q1", count: 1234, avg_spend: 1500.50, avg_nights: 8.2 },
      { quarter: "2023-Q2", count: 1100, avg_spend: 1400.00, avg_nights: 7.8 },
    ],
  },
  {
    nationality: "Germany",
    data: [
      { quarter: "2023-Q1", count: 900, avg_spend: 1200.00, avg_nights: 9.0 },
      { quarter: "2023-Q2", count: 950, avg_spend: 1250.00, avg_nights: 8.5 },
    ],
  },
];

import ProfilesPage from "./ProfilesPage";

function renderPage(initialEntries: string[] = ["/"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <ProfilesPage />
    </MemoryRouter>
  );
}

describe("ProfilesPage URL state persistence", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders without a pre-selected cluster by default", () => {
    renderPage();
    // useProfileDetail should be called with null when no cluster is selected
    expect(mockUseProfileDetail).toHaveBeenCalledWith(null);
  });

  it("restores selected cluster from URL params", () => {
    renderPage(["/profiles?cluster=1"]);
    // useProfileDetail should be called with cluster id 1
    expect(mockUseProfileDetail).toHaveBeenCalledWith(1);
  });

  it("renders the cluster visualization", () => {
    renderPage();
    expect(screen.getByTestId("cluster-viz")).toBeInTheDocument();
  });
});

describe("ProfilesPage Market Trends panel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockTrendsReturn = { data: null, error: null, loading: false, refetch: vi.fn() };
  });

  it("does not render market trends table when data is null", () => {
    renderPage();
    expect(screen.queryByText("Market Trends")).not.toBeInTheDocument();
  });

  it("renders market trends table when trends data is available", () => {
    mockTrendsReturn = {
      data: fakeTrendsData,
      loading: false,
      error: null,
      refetch: vi.fn(),
    };

    render(
      <MemoryRouter>
        <ProfilesPage />
      </MemoryRouter>
    );

    // The panel title should be rendered with the English translation
    expect(screen.getByText("Market Trends")).toBeInTheDocument();
    // Quarter values should appear
    expect(screen.getByText("2023-Q1")).toBeInTheDocument();
    expect(screen.getByText("2023-Q2")).toBeInTheDocument();
    // Nationality headers
    expect(screen.getByText("United Kingdom")).toBeInTheDocument();
    expect(screen.getByText("Germany")).toBeInTheDocument();
  });
});
