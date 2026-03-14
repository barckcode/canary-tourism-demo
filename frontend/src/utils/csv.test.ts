import { describe, it, expect, vi, beforeEach } from "vitest";
import { generateCSV, downloadCSV, exportCSV } from "./csv";

describe("generateCSV", () => {
  it("generates CSV with headers and rows", () => {
    const csv = generateCSV(
      ["Name", "Value"],
      [
        ["Arrivals", 150000],
        ["Occupancy", 78.5],
      ]
    );
    expect(csv).toBe("Name,Value\nArrivals,150000\nOccupancy,78.5");
  });

  it("includes metadata as comment lines", () => {
    const csv = generateCSV(["A", "B"], [["x", 1]], {
      source: "Test Source",
      generatedAt: "2026-01-15T10:00:00Z",
      filters: { indicator: "turistas", geo: "ES709" },
    });
    const lines = csv.split("\n");
    expect(lines[0]).toBe("# Generated: 2026-01-15T10:00:00Z");
    expect(lines[1]).toBe("# Source: Test Source");
    expect(lines[2]).toBe("# Filters: indicator=turistas; geo=ES709");
    expect(lines[3]).toBe("#");
    expect(lines[4]).toBe("A,B");
    expect(lines[5]).toBe("x,1");
  });

  it("uses current timestamp when generatedAt is not provided", () => {
    const csv = generateCSV(["A"], [[1]], { source: "Test" });
    const firstLine = csv.split("\n")[0];
    expect(firstLine).toMatch(/^# Generated: \d{4}-\d{2}-\d{2}T/);
  });

  it("escapes fields containing commas", () => {
    const csv = generateCSV(["Name"], [["Hello, World"]]);
    expect(csv).toBe('Name\n"Hello, World"');
  });

  it("escapes fields containing double quotes", () => {
    const csv = generateCSV(["Name"], [['He said "hi"']]);
    expect(csv).toBe('Name\n"He said ""hi"""');
  });

  it("escapes fields containing newlines", () => {
    const csv = generateCSV(["Name"], [["Line1\nLine2"]]);
    expect(csv).toBe('Name\n"Line1\nLine2"');
  });

  it("handles empty rows", () => {
    const csv = generateCSV(["A", "B"], []);
    expect(csv).toBe("A,B");
  });
});

describe("downloadCSV", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("creates a blob, triggers download, and cleans up", () => {
    const mockClick = vi.fn();
    const mockRemoveChild = vi.fn();
    const mockAppendChild = vi.fn();
    const mockRevokeObjectURL = vi.fn();

    const mockCreateElement = vi.spyOn(document, "createElement").mockReturnValue({
      href: "",
      download: "",
      style: { display: "" },
      click: mockClick,
    } as unknown as HTMLAnchorElement);

    vi.spyOn(document.body, "appendChild").mockImplementation(mockAppendChild);
    vi.spyOn(document.body, "removeChild").mockImplementation(mockRemoveChild);

    const mockUrl = "blob:http://localhost/test-id";
    vi.spyOn(URL, "createObjectURL").mockReturnValue(mockUrl);
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(mockRevokeObjectURL);

    downloadCSV("a,b\n1,2", "test.csv");

    expect(mockCreateElement).toHaveBeenCalledWith("a");
    expect(mockClick).toHaveBeenCalled();
    expect(mockAppendChild).toHaveBeenCalled();
    expect(mockRemoveChild).toHaveBeenCalled();
    expect(mockRevokeObjectURL).toHaveBeenCalledWith(mockUrl);
  });

  it("appends .csv extension if missing", () => {
    const link = {
      href: "",
      download: "",
      style: { display: "" },
      click: vi.fn(),
    } as unknown as HTMLAnchorElement;

    vi.spyOn(document, "createElement").mockReturnValue(link);
    vi.spyOn(document.body, "appendChild").mockImplementation(() => link);
    vi.spyOn(document.body, "removeChild").mockImplementation(() => link);
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});

    downloadCSV("data", "myfile");
    expect(link.download).toBe("myfile.csv");
  });
});

describe("exportCSV", () => {
  it("generates and downloads in one call", () => {
    const mockClick = vi.fn();
    const link = {
      href: "",
      download: "",
      style: { display: "" },
      click: mockClick,
    } as unknown as HTMLAnchorElement;

    vi.spyOn(document, "createElement").mockReturnValue(link);
    vi.spyOn(document.body, "appendChild").mockImplementation(() => link);
    vi.spyOn(document.body, "removeChild").mockImplementation(() => link);
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});

    exportCSV(["Col"], [["val"]], "export.csv");
    expect(mockClick).toHaveBeenCalled();
    expect(link.download).toBe("export.csv");
  });
});
