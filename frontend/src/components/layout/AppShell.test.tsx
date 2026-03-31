import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AppShell from "./AppShell";

function renderAppShell(children = <div>Page content</div>) {
  return render(
    <MemoryRouter>
      <AppShell>{children}</AppShell>
    </MemoryRouter>
  );
}

// Helper to simulate a specific viewport width via matchMedia
function mockMatchMedia(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

describe("AppShell", () => {
  beforeEach(() => {
    mockMatchMedia(true);
  });

  describe("Skip navigation link", () => {
    it("renders a skip navigation link as the first focusable element", () => {
      renderAppShell();
      const skipLink = screen.getByText("Skip to main content");
      expect(skipLink).toBeInTheDocument();
      expect(skipLink).toHaveAttribute("href", "#main-content");
      expect(skipLink.tagName).toBe("A");
    });

    it("skip link targets the main content area", () => {
      renderAppShell();
      const main = document.getElementById("main-content");
      expect(main).not.toBeNull();
      expect(main?.tagName).toBe("MAIN");
    });

    it("skip link has sr-only class by default", () => {
      renderAppShell();
      const skipLink = screen.getByText("Skip to main content");
      expect(skipLink.className).toContain("sr-only");
    });
  });

  describe("Main content area", () => {
    it("renders children inside main", () => {
      renderAppShell(<div>Test page content</div>);
      const main = document.getElementById("main-content")!;
      expect(within(main).getByText("Test page content")).toBeInTheDocument();
    });

    it("main element has id=main-content", () => {
      renderAppShell();
      const main = document.getElementById("main-content");
      expect(main).not.toBeNull();
      expect(main?.tagName).toBe("MAIN");
    });
  });

  describe("Mobile hamburger button", () => {
    it("renders a hamburger button for opening the mobile menu", () => {
      renderAppShell();
      const hamburger = screen.getByLabelText("Open navigation menu");
      expect(hamburger).toBeInTheDocument();
    });

    it("opens mobile drawer when hamburger is clicked", () => {
      renderAppShell();
      const hamburger = screen.getByLabelText("Open navigation menu");
      fireEvent.click(hamburger);

      const drawer = screen.getByRole("dialog");
      expect(drawer).toBeInTheDocument();
      expect(drawer).toHaveAttribute("aria-modal", "true");
    });

    it("closes mobile drawer when close button is clicked", async () => {
      renderAppShell();
      fireEvent.click(screen.getByLabelText("Open navigation menu"));
      expect(screen.getByRole("dialog")).toBeInTheDocument();

      fireEvent.click(screen.getByLabelText("Close navigation menu"));
      // AnimatePresence exit animations may keep the element briefly in the DOM.
      // We use waitFor to wait until the dialog is removed.
      const { waitFor } = await import("@testing-library/react");
      await waitFor(() => {
        expect(screen.queryByRole("dialog")).toBeNull();
      });
    });
  });

  describe("Desktop sidebar", () => {
    it("renders collapse/expand toggle button", () => {
      renderAppShell();
      const toggle = screen.getByLabelText("Collapse sidebar");
      expect(toggle).toBeInTheDocument();
    });

    it("toggles collapse state when the button is clicked", () => {
      renderAppShell();
      const toggle = screen.getByLabelText("Collapse sidebar");
      fireEvent.click(toggle);
      expect(screen.getByLabelText("Expand sidebar")).toBeInTheDocument();
    });
  });

  describe("Navigation items", () => {
    it("renders all navigation links", () => {
      renderAppShell();
      expect(screen.getAllByText("Dashboard").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Predictions").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Profiles").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Data Explorer").length).toBeGreaterThanOrEqual(1);
    });
  });

  describe("Accessibility", () => {
    it("mobile drawer has proper ARIA attributes", () => {
      renderAppShell();
      fireEvent.click(screen.getByLabelText("Open navigation menu"));

      const drawer = screen.getByRole("dialog");
      expect(drawer).toHaveAttribute("aria-modal", "true");
      expect(drawer).toHaveAttribute("aria-label", "Navigation menu");
    });

    it("navigation has aria-label", () => {
      renderAppShell();
      const navs = screen.getAllByRole("navigation", { name: "Main navigation" });
      expect(navs.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe("Footer", () => {
    it("renders GitHub link and About link", () => {
      renderAppShell();
      expect(screen.getByLabelText("View source on GitHub")).toBeInTheDocument();
      // About link appears in both sidebar nav and footer
      const aboutLinks = screen.getAllByText("About this project");
      expect(aboutLinks.length).toBeGreaterThanOrEqual(1);
    });
  });
});
