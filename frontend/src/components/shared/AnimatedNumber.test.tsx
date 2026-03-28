import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import AnimatedNumber from "./AnimatedNumber";

// Mock framer-motion's useReducedMotion hook
const mockUseReducedMotion = vi.fn(() => false);
vi.mock("framer-motion", async () => {
  const actual = await vi.importActual("framer-motion");
  return {
    ...actual,
    useReducedMotion: () => mockUseReducedMotion(),
  };
});

describe("AnimatedNumber", () => {
  it("renders em dash for NaN", () => {
    render(<AnimatedNumber value={NaN} />);
    expect(screen.getByText("\u2014")).toBeInTheDocument();
  });

  it("renders em dash for Infinity", () => {
    render(<AnimatedNumber value={Infinity} />);
    expect(screen.getByText("\u2014")).toBeInTheDocument();
  });

  it("renders em dash for negative Infinity", () => {
    render(<AnimatedNumber value={-Infinity} />);
    expect(screen.getByText("\u2014")).toBeInTheDocument();
  });

  it("renders em dash when value is null", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    render(<AnimatedNumber value={null as any} />);
    expect(screen.getByText("\u2014")).toBeInTheDocument();
  });

  it("renders em dash when value is undefined", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    render(<AnimatedNumber value={undefined as any} />);
    expect(screen.getByText("\u2014")).toBeInTheDocument();
  });

  it("renders a valid number without em dash", () => {
    render(<AnimatedNumber value={42} />);
    // The initial render shows format(0) = "0", then animates to 42
    const span = screen.getByText(/\d/);
    expect(span).toBeInTheDocument();
    expect(span.textContent).not.toBe("\u2014");
  });

  it("displays final value immediately when prefers-reduced-motion is set", () => {
    mockUseReducedMotion.mockReturnValue(true);
    render(<AnimatedNumber value={1234} />);
    expect(screen.getByText("1,234")).toBeInTheDocument();
    // Should render a plain span, not a motion.span
    const span = screen.getByText("1,234");
    expect(span.tagName).toBe("SPAN");
    mockUseReducedMotion.mockReturnValue(false);
  });

  it("uses custom format with reduced motion", () => {
    mockUseReducedMotion.mockReturnValue(true);
    const format = (n: number) => `${n.toFixed(1)}%`;
    render(<AnimatedNumber value={85} format={format} />);
    expect(screen.getByText("85.0%")).toBeInTheDocument();
    mockUseReducedMotion.mockReturnValue(false);
  });
});
