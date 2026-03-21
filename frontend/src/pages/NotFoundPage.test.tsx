import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";
import NotFoundPage from "./NotFoundPage";

function renderWithRouter() {
  return render(
    <MemoryRouter>
      <NotFoundPage />
    </MemoryRouter>
  );
}

describe("NotFoundPage", () => {
  it("renders the 404 heading", () => {
    renderWithRouter();
    expect(screen.getByText("404")).toBeInTheDocument();
  });

  it("renders the translated title and message", () => {
    renderWithRouter();
    expect(screen.getByText("Page not found")).toBeInTheDocument();
    expect(
      screen.getByText("The page you're looking for doesn't exist")
    ).toBeInTheDocument();
  });

  it("renders a link back to the dashboard", () => {
    renderWithRouter();
    const link = screen.getByRole("link", { name: /back to dashboard/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/");
  });
});
