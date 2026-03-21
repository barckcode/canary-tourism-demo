import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import AnimatedNumber from "./AnimatedNumber";

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
});
