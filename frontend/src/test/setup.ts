import "@testing-library/jest-dom/vitest";
import i18n from "../i18n";

// Set test language to English for consistent test assertions
i18n.changeLanguage("en");

// Mock window.matchMedia for tests (used by reduced-motion checks)
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});
