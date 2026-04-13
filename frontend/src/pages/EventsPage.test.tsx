import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

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
const mockUseEvents = vi.fn();
const mockUseEventCategories = vi.fn();
const mockRefetchEvents = vi.fn();

vi.mock("../api/hooks", () => ({
  useEvents: (...args: unknown[]) => mockUseEvents(...args),
  useEventCategories: () => mockUseEventCategories(),
  useEventImpact: () => ({ data: null, loading: false, error: null }),
}));

// Mock the API client for create/delete mutations
const mockApiCreate = vi.fn();
const mockApiDelete = vi.fn();

vi.mock("../api/client", () => ({
  api: {
    events: {
      create: (...args: unknown[]) => mockApiCreate(...args),
      delete: (...args: unknown[]) => mockApiDelete(...args),
    },
  },
}));

import EventsPage from "./EventsPage";

function renderPage() {
  return render(<EventsPage />);
}

const fakeEvents = [
  {
    id: 1,
    name: "Carnival of Santa Cruz",
    description: "Annual carnival celebration",
    category: "cultural",
    start_date: "2025-02-15",
    end_date: "2025-03-02",
    impact_estimate: "High",
    location: "Santa Cruz",
    source: "system",
    created_at: "2025-01-01T00:00:00Z",
  },
  {
    id: 2,
    name: "New Flight Route London-TFS",
    description: "Weekly direct flights",
    category: "connectivity",
    start_date: "2025-02-01",
    end_date: undefined,
    impact_estimate: undefined,
    location: "Tenerife South Airport",
    source: "user",
    created_at: "2025-01-15T00:00:00Z",
  },
  {
    id: 3,
    name: "Summer Festival",
    description: "Music and arts festival",
    category: "cultural",
    start_date: "2025-07-10",
    end_date: "2025-07-15",
    impact_estimate: "Medium",
    location: "Adeje",
    source: "system",
    created_at: "2025-01-20T00:00:00Z",
  },
];

const fakeCategories = ["cultural", "connectivity", "regulation", "external"];

describe("EventsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseEvents.mockReturnValue({
      data: { events: fakeEvents },
      loading: false,
      error: null,
      refetch: mockRefetchEvents,
    });
    mockUseEventCategories.mockReturnValue({
      data: { categories: fakeCategories },
    });
  });

  it("renders the page title and subtitle", () => {
    renderPage();
    expect(screen.getByText("Tourism Events Calendar")).toBeInTheDocument();
    expect(
      screen.getByText("Events, festivals, and external factors affecting tourism demand")
    ).toBeInTheDocument();
  });

  it("renders event list when data loads", () => {
    renderPage();
    expect(screen.getByText("Carnival of Santa Cruz")).toBeInTheDocument();
    expect(screen.getByText("New Flight Route London-TFS")).toBeInTheDocument();
    expect(screen.getByText("Summer Festival")).toBeInTheDocument();
  });

  it("shows loading state while data fetches", () => {
    mockUseEvents.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: mockRefetchEvents,
    });
    renderPage();
    expect(screen.getByText("Loading...")).toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("shows error state when API fails", () => {
    mockUseEvents.mockReturnValue({
      data: null,
      loading: false,
      error: "Network error",
      refetch: mockRefetchEvents,
    });
    renderPage();
    expect(
      screen.getByText("Failed to load data. Please try again.")
    ).toBeInTheDocument();
  });

  it("groups events by month", () => {
    renderPage();
    // Feb 2025 group should contain both events with start_date in Feb
    const headings = screen.getAllByRole("heading", { level: 2 });
    const monthLabels = headings.map((h) => h.textContent);
    // Should have February 2025 and July 2025
    expect(monthLabels.some((l) => l?.includes("February") && l?.includes("2025"))).toBe(true);
    expect(monthLabels.some((l) => l?.includes("July") && l?.includes("2025"))).toBe(true);
  });

  it("shows event cards with name, dates, and category badge", () => {
    renderPage();
    // Event name
    expect(screen.getByText("Carnival of Santa Cruz")).toBeInTheDocument();
    // Category badge translated
    const culturalBadges = screen.getAllByText("Cultural");
    expect(culturalBadges.length).toBeGreaterThanOrEqual(1);
    const connectivityMatches = screen.getAllByText("Connectivity");
    expect(connectivityMatches.length).toBeGreaterThanOrEqual(1);
    // Location
    expect(screen.getByText("Santa Cruz")).toBeInTheDocument();
    // Impact
    expect(screen.getByText(/Estimated impact.*High/)).toBeInTheDocument();
  });

  it("shows 'no events' message when list is empty", () => {
    mockUseEvents.mockReturnValue({
      data: { events: [] },
      loading: false,
      error: null,
      refetch: mockRefetchEvents,
    });
    renderPage();
    expect(screen.getByText("No events in this period")).toBeInTheDocument();
  });

  describe("category filter", () => {
    it("renders all category filter buttons", () => {
      renderPage();
      expect(screen.getByText("All")).toBeInTheDocument();
      // Category buttons in the filter group
      const filterGroup = screen.getByRole("group", { name: "Category" });
      expect(filterGroup).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Cultural" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Connectivity" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Regulation" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "External" })).toBeInTheDocument();
    });

    it("has 'All' selected by default with aria-pressed", () => {
      renderPage();
      const allButton = screen.getByRole("button", { name: "All" });
      expect(allButton).toHaveAttribute("aria-pressed", "true");
    });

    it("calls useEvents with selected category when clicking a filter", () => {
      renderPage();
      const culturalButton = screen.getByRole("button", { name: "Cultural" });
      fireEvent.click(culturalButton);
      // useEvents should have been called with the category
      expect(mockUseEvents).toHaveBeenCalledWith(
        undefined,
        undefined,
        "cultural"
      );
    });

    it("deselects category when clicking the active filter again", () => {
      renderPage();
      // Verify initial call has no category
      expect(mockUseEvents).toHaveBeenCalledWith(undefined, undefined, undefined);
      // Click Cultural filter
      const culturalFilterBtn = screen.getByRole("button", { name: "Cultural" });
      fireEvent.click(culturalFilterBtn);
      // After state update and re-render, useEvents should be called with "cultural"
      expect(mockUseEvents).toHaveBeenCalledWith(undefined, undefined, "cultural");
      // Click Cultural again to deselect -- the same button element
      fireEvent.click(screen.getByRole("button", { name: "Cultural" }));
      // The last call should be back to undefined
      const lastCall = mockUseEvents.mock.calls[mockUseEvents.mock.calls.length - 1];
      expect(lastCall[2]).toBeUndefined();
    });
  });

  describe("delete event", () => {
    it("shows delete button only for user-created events", () => {
      renderPage();
      // Only event id=2 is user-created
      const deleteButtons = screen.getAllByRole("button", { name: /Delete/ });
      // The delete buttons from EventCard (not the filter buttons)
      const eventDeleteButtons = deleteButtons.filter((btn) =>
        btn.getAttribute("aria-label")?.includes("Delete")
      );
      expect(eventDeleteButtons).toHaveLength(1);
      expect(eventDeleteButtons[0]).toHaveAttribute(
        "aria-label",
        "Delete New Flight Route London-TFS"
      );
    });

    it("calls api.events.delete and refetches on success", async () => {
      mockApiDelete.mockResolvedValue({});
      renderPage();
      const deleteButton = screen.getByRole("button", {
        name: /Delete New Flight Route/,
      });
      fireEvent.click(deleteButton);
      await waitFor(() => {
        expect(mockApiDelete).toHaveBeenCalledWith(2);
      });
      await waitFor(() => {
        expect(mockRefetchEvents).toHaveBeenCalled();
      });
    });

    it("shows error message when delete fails", async () => {
      mockApiDelete.mockRejectedValue(new Error("Server error"));
      renderPage();
      const deleteButton = screen.getByRole("button", {
        name: /Delete New Flight Route/,
      });
      fireEvent.click(deleteButton);
      await waitFor(() => {
        expect(screen.getByRole("alert")).toHaveTextContent("Failed to delete");
      });
    });
  });

  describe("create event", () => {
    it("toggles the add event form when clicking 'Add Event'", () => {
      renderPage();
      // Form should not be visible initially
      expect(screen.queryByLabelText("Event name *")).not.toBeInTheDocument();
      // Click add button
      const addButton = screen.getByRole("button", { name: "Add Event" });
      fireEvent.click(addButton);
      // Form should now be visible
      expect(screen.getByLabelText("Event name *")).toBeInTheDocument();
    });

    it("submits the form and refetches events on success", async () => {
      mockApiCreate.mockResolvedValue({ id: 10 });
      renderPage();
      // Open form
      fireEvent.click(screen.getByRole("button", { name: "Add Event" }));
      // Fill required fields
      fireEvent.change(screen.getByLabelText("Event name *"), {
        target: { value: "Test Event" },
      });
      fireEvent.change(screen.getByLabelText("Start date *"), {
        target: { value: "2025-06-01" },
      });
      // Submit
      fireEvent.click(screen.getByRole("button", { name: "Save" }));
      await waitFor(() => {
        expect(mockApiCreate).toHaveBeenCalledWith(
          expect.objectContaining({
            name: "Test Event",
            start_date: "2025-06-01",
            category: "cultural",
          })
        );
      });
      await waitFor(() => {
        expect(mockRefetchEvents).toHaveBeenCalled();
      });
    });

    it("shows error message when create fails", async () => {
      mockApiCreate.mockRejectedValue(new Error("Validation error"));
      renderPage();
      // Open form
      fireEvent.click(screen.getByRole("button", { name: "Add Event" }));
      // Fill required fields
      fireEvent.change(screen.getByLabelText("Event name *"), {
        target: { value: "Failing Event" },
      });
      fireEvent.change(screen.getByLabelText("Start date *"), {
        target: { value: "2025-06-01" },
      });
      // Submit
      fireEvent.click(screen.getByRole("button", { name: "Save" }));
      await waitFor(() => {
        expect(screen.getByRole("alert")).toHaveTextContent("Failed to create");
      });
    });

    it("hides the form when clicking cancel", () => {
      renderPage();
      fireEvent.click(screen.getByRole("button", { name: "Add Event" }));
      expect(screen.getByLabelText("Event name *")).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
      expect(screen.queryByLabelText("Event name *")).not.toBeInTheDocument();
    });
  });
});
