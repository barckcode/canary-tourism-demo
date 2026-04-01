import { lazy, Suspense, useState, useEffect } from "react";
import { Routes, Route, useLocation } from "react-router-dom";
import { MotionConfig } from "framer-motion";
import { useTranslation } from "react-i18next";
import AppShell from "./components/layout/AppShell";
import ErrorBoundary from "./components/shared/ErrorBoundary";

const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const ForecastPage = lazy(() => import("./pages/ForecastPage"));
const ProfilesPage = lazy(() => import("./pages/ProfilesPage"));
const DataExplorerPage = lazy(() => import("./pages/DataExplorerPage"));
const EventsPage = lazy(() => import("./pages/EventsPage"));
const AboutPage = lazy(() => import("./pages/AboutPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));

function PageLoader() {
  const { t } = useTranslation();
  return (
    <div className="flex items-center justify-center h-[60vh]" role="status" aria-live="polite" aria-busy="true">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-ocean-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-sm text-gray-400">{t('common.loading')}</span>
        <span className="sr-only">{t('common.loadingPageContent')}</span>
      </div>
    </div>
  );
}

function RouteAnnouncer() {
  const location = useLocation();
  const { t } = useTranslation();
  const [announcement, setAnnouncement] = useState("");

  useEffect(() => {
    const routeNames: Record<string, string> = {
      "/": t("nav.dashboard"),
      "/forecast": t("nav.predictions"),
      "/profiles": t("nav.profiles"),
      "/data": t("nav.dataExplorer"),
      "/events": t("nav.events"),
      "/about": t("nav.aboutProject"),
    };
    const pageName = routeNames[location.pathname] || "";
    if (pageName) {
      setAnnouncement(t("accessibility.navigatedTo", { page: pageName }));
    }
  }, [location.pathname, t]);

  return (
    <div aria-live="polite" aria-atomic="true" className="sr-only">
      {announcement}
    </div>
  );
}

function App() {
  return (
    <MotionConfig reducedMotion="user">
      <RouteAnnouncer />
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
              path="/events"
              element={
                <ErrorBoundary>
                  <EventsPage />
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
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </AppShell>
    </MotionConfig>
  );
}

export default App;
