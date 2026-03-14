import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ExportCSVButton from "./ExportCSVButton";

// Mock the csv utility to avoid DOM side effects in tests
vi.mock("../../utils/csv", () => ({
  exportCSV: vi.fn(),
}));

import { exportCSV } from "../../utils/csv";

describe("ExportCSVButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders with default label", () => {
    render(
      <ExportCSVButton
        headers={["A"]}
        rows={[["1"]]}
        filename="test"
      />
    );
    expect(screen.getByText("Export CSV")).toBeInTheDocument();
  });

  it("has accessible aria-label", () => {
    render(
      <ExportCSVButton
        headers={["A"]}
        rows={[["1"]]}
        filename="test"
        ariaLabel="Download tourism data"
      />
    );
    expect(screen.getByRole("button")).toHaveAttribute(
      "aria-label",
      "Download tourism data"
    );
  });

  it("calls exportCSV on click with correct arguments", () => {
    const headers = ["Name", "Value"];
    const rows: (string | number)[][] = [["Arrivals", 150000]];
    const metadata = { source: "Test" };

    render(
      <ExportCSVButton
        headers={headers}
        rows={rows}
        filename="test-export"
        metadata={metadata}
      />
    );

    fireEvent.click(screen.getByRole("button"));
    expect(exportCSV).toHaveBeenCalledWith(headers, rows, "test-export", metadata);
  });

  it("is disabled when disabled prop is true", () => {
    render(
      <ExportCSVButton
        headers={["A"]}
        rows={[["1"]]}
        filename="test"
        disabled
      />
    );

    const button = screen.getByRole("button");
    expect(button).toBeDisabled();

    fireEvent.click(button);
    expect(exportCSV).not.toHaveBeenCalled();
  });

  it("is disabled when rows are empty", () => {
    render(
      <ExportCSVButton
        headers={["A"]}
        rows={[]}
        filename="test"
      />
    );

    const button = screen.getByRole("button");
    expect(button).toBeDisabled();
  });

  it("shows 'Exported' text after click", async () => {
    render(
      <ExportCSVButton
        headers={["A"]}
        rows={[["1"]]}
        filename="test"
      />
    );

    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Exported")).toBeInTheDocument();
  });
});
