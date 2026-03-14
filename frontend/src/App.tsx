import { lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import ErrorBoundary from "./components/shared/ErrorBoundary";

const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const ForecastPage = lazy(() => import("./pages/ForecastPage"));
const ProfilesPage = lazy(() => import("./pages/ProfilesPage"));
const DataExplorerPage = lazy(() => import("./pages/DataExplorerPage"));
const AboutPage = lazy(() => import("./pages/AboutPage"));

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-[60vh]" role="status" aria-live="polite">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-ocean-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-sm text-gray-400">Loading...</span>
        <span className="sr-only">Loading page content</span>
      </div>
    </div>
  );
}

function App() {
  return (
    <AppShell>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route
            path="/"
            element={
              <ErrorBoundary>
                <DashboardPage />
              </ErrorBoundary>
            }
          />
          <Route
            path="/forecast"
            element={
              <ErrorBoundary>
                <ForecastPage />
              </ErrorBoundary>
            }
          />
          <Route
            path="/profiles"
            element={
              <ErrorBoundary>
                <ProfilesPage />
              </ErrorBoundary>
            }
          />
          <Route
            path="/data"
            element={
              <ErrorBoundary>
                <DataExplorerPage />
              </ErrorBoundary>
            }
          />
          <Route
            path="/about"
            element={
              <ErrorBoundary>
                <AboutPage />
              </ErrorBoundary>
            }
          />
        </Routes>
      </Suspense>
    </AppShell>
  );
}

export default App;
