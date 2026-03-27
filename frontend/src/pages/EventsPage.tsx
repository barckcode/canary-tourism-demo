import { useState, useMemo, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useTranslation } from "react-i18next";
import { stagger, fadeUp } from "../utils/animations";
import Panel from "../components/layout/Panel";
import ErrorState from "../components/shared/ErrorState";
import { useEvents, useEventCategories, useEventImpact, type TourismEvent } from "../api/hooks";
import { api } from "../api/client";

const CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  cultural: { bg: "bg-tropical-500/20", text: "text-tropical-400", border: "border-tropical-500/40" },
  connectivity: { bg: "bg-ocean-400/20", text: "text-ocean-400", border: "border-ocean-400/40" },
  regulation: { bg: "bg-amber-500/20", text: "text-amber-400", border: "border-amber-500/40" },
  external: { bg: "bg-rose-500/20", text: "text-rose-400", border: "border-rose-500/40" },
};

function getCategoryStyle(category: string) {
  return CATEGORY_COLORS[category] || CATEGORY_COLORS.external;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function getMonthKey(dateStr: string): string {
  const date = new Date(dateStr);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function formatMonthLabel(monthKey: string): string {
  const [year, month] = monthKey.split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleDateString(undefined, { year: "numeric", month: "long" });
}

const INDICATOR_LABELS: Record<string, string> = {
  turistas: "Turistas",
  alojatur_ocupacion: "Ocupacion",
  alojatur_adr: "ADR",
  alojatur_revpar: "RevPAR",
  alojatur_pernoctaciones: "Pernoctaciones",
};

function formatIndicatorValue(indicator: string, value: number): string {
  if (indicator === "alojatur_ocupacion") return `${value.toFixed(1)}%`;
  if (indicator === "alojatur_adr" || indicator === "alojatur_revpar") return `${value.toFixed(2)}`;
  return value.toLocaleString();
}

function EventImpactPanel({ eventId, t }: { eventId: number; t: (key: string) => string }) {
  const { data, loading, error } = useEventImpact(eventId);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-6" role="status" aria-live="polite">
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 border-2 border-ocean-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs text-gray-400">{t("common.loading")}</span>
        </div>
      </div>
    );
  }

  if (error || !data || Object.keys(data.yoy_changes).length === 0) {
    return (
      <div className="py-4 text-center">
        <p className="text-xs text-gray-500">{t("events.impact_kpi.noData")}</p>
      </div>
    );
  }

  const currentMap = new Map(data.current_kpis.map((k) => [k.indicator, k.value]));
  const previousMap = new Map(data.previous_year_kpis.map((k) => [k.indicator, k.value]));
  const indicators = Object.keys(data.yoy_changes);

  return (
    <div className="mt-3 pt-3 border-t border-gray-700/50">
      <h5 className="text-xs font-semibold text-gray-300 mb-2">{t("events.impact_kpi.title")}</h5>
      <div className="overflow-x-auto">
        <table className="w-full text-xs" aria-label={t("events.impact_kpi.title")}>
          <thead>
            <tr className="text-gray-500">
              <th className="text-left py-1 pr-4 font-medium">{t("events.impact_kpi.indicator")}</th>
              <th className="text-right py-1 px-2 font-medium">{t("events.impact_kpi.currentYear")}</th>
              <th className="text-right py-1 px-2 font-medium">{t("events.impact_kpi.previousYear")}</th>
              <th className="text-right py-1 pl-2 font-medium">{t("events.impact_kpi.yoyChange")}</th>
            </tr>
          </thead>
          <tbody>
            {indicators.map((ind) => {
              const yoy = data.yoy_changes[ind];
              const current = currentMap.get(ind);
              const previous = previousMap.get(ind);
              const isPositive = yoy >= 0;
              return (
                <tr key={ind} className="border-t border-gray-800/50">
                  <td className="py-1.5 pr-4 text-gray-300 font-medium">
                    {INDICATOR_LABELS[ind] || ind}
                  </td>
                  <td className="py-1.5 px-2 text-right text-gray-300 tabular-nums">
                    {current !== undefined ? formatIndicatorValue(ind, current) : "-"}
                  </td>
                  <td className="py-1.5 px-2 text-right text-gray-400 tabular-nums">
                    {previous !== undefined ? formatIndicatorValue(ind, previous) : "-"}
                  </td>
                  <td
                    className={`py-1.5 pl-2 text-right font-semibold tabular-nums ${
                      isPositive ? "text-emerald-400" : "text-rose-400"
                    }`}
                  >
                    {isPositive ? "+" : ""}{yoy.toFixed(1)}%
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

interface EventFormData {
  name: string;
  description: string;
  category: string;
  start_date: string;
  end_date: string;
  impact_estimate: string;
  location: string;
}

const EMPTY_FORM: EventFormData = {
  name: "",
  description: "",
  category: "cultural",
  start_date: "",
  end_date: "",
  impact_estimate: "",
  location: "",
};

function EventCard({
  event,
  onDelete,
  t,
  isExpanded,
  onToggleExpand,
}: {
  event: TourismEvent;
  onDelete: (id: number) => void;
  t: (key: string) => string;
  isExpanded: boolean;
  onToggleExpand: () => void;
}) {
  const style = getCategoryStyle(event.category);
  const isUserCreated = event.source === "user";

  return (
    <div className="rounded-lg bg-gray-800/30 border border-gray-700/50 hover:border-gray-600/50 transition-colors">
      <button
        type="button"
        onClick={onToggleExpand}
        className="w-full text-left p-4 focus:outline-none focus:ring-2 focus:ring-ocean-500/40 rounded-lg"
        aria-expanded={isExpanded}
        aria-label={`${event.name} - ${t("events.impact_kpi.title")}`}
      >
        <div className="flex items-start gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h4 className="text-sm font-semibold text-white truncate">{event.name}</h4>
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium uppercase tracking-wider border ${style.bg} ${style.text} ${style.border}`}
              >
                {t(`events.${event.category}`)}
              </span>
              {isUserCreated && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium uppercase tracking-wider border bg-gray-700/40 text-gray-400 border-gray-600/40">
                  {t("events.userCreated")}
                </span>
              )}
            </div>
            {event.description && (
              <p className="text-xs text-gray-400 mt-1 line-clamp-2">{event.description}</p>
            )}
            <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
              <span>
                {formatDate(event.start_date)}
                {event.end_date && ` - ${formatDate(event.end_date)}`}
              </span>
              {event.location && (
                <span className="flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  {event.location}
                </span>
              )}
              {event.impact_estimate && (
                <span className="flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                  {t("events.impact")}: {event.impact_estimate}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {isUserCreated && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(event.id);
                }}
                className="px-3 py-1.5 text-xs font-medium rounded-lg text-rose-400 hover:text-white hover:bg-rose-500/20 border border-rose-500/30 hover:border-rose-500/50 transition-colors"
                aria-label={`${t("events.deleteEvent")} ${event.name}`}
              >
                {t("events.deleteEvent")}
              </button>
            )}
            <svg
              className={`w-4 h-4 text-gray-500 transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>
      </button>
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden px-4 pb-4"
          >
            <EventImpactPanel eventId={event.id} t={t} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function EventsPage() {
  const { t } = useTranslation();
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<EventFormData>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [expandedEventId, setExpandedEventId] = useState<number | null>(null);

  const {
    data: eventsData,
    loading: eventsLoading,
    error: eventsError,
    refetch: refetchEvents,
  } = useEvents(undefined, undefined, selectedCategory || undefined);

  const { data: categoriesData } = useEventCategories();

  const categories = categoriesData?.categories || ["cultural", "connectivity", "regulation", "external"];

  const groupedEvents = useMemo(() => {
    if (!eventsData?.events) return new Map<string, TourismEvent[]>();
    const sorted = [...eventsData.events].sort(
      (a, b) => new Date(a.start_date).getTime() - new Date(b.start_date).getTime()
    );
    const groups = new Map<string, TourismEvent[]>();
    for (const event of sorted) {
      const key = getMonthKey(event.start_date);
      const existing = groups.get(key) || [];
      existing.push(event);
      groups.set(key, existing);
    }
    return groups;
  }, [eventsData]);

  const handleDelete = useCallback(
    async (id: number) => {
      try {
        await api.events.delete(id);
        refetchEvents();
      } catch {
        // Silently fail - event might already be deleted
      }
    },
    [refetchEvents]
  );

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!formData.name || !formData.start_date) return;
      setSubmitting(true);
      try {
        await api.events.create({
          name: formData.name,
          description: formData.description || undefined,
          category: formData.category,
          start_date: formData.start_date,
          end_date: formData.end_date || undefined,
          impact_estimate: formData.impact_estimate || undefined,
          location: formData.location || undefined,
        });
        setFormData(EMPTY_FORM);
        setShowForm(false);
        refetchEvents();
      } catch {
        // Error creating event
      } finally {
        setSubmitting(false);
      }
    },
    [formData, refetchEvents]
  );

  const updateField = useCallback(
    (field: keyof EventFormData, value: string) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
    },
    []
  );

  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      {/* Header */}
      <motion.div variants={fadeUp} className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold gradient-text">{t("events.title")}</h1>
          <p className="text-sm text-gray-400 mt-1">{t("events.subtitle")}</p>
        </div>
        <button
          onClick={() => setShowForm((prev) => !prev)}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-ocean-500/20 text-ocean-400 border border-ocean-500/30 hover:bg-ocean-500/30 hover:border-ocean-500/50 transition-colors"
          aria-label={t("events.addEvent")}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          {t("events.addEvent")}
        </button>
      </motion.div>

      {/* Add Event Form */}
      <AnimatePresence>
        {showForm && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            className="overflow-hidden"
          >
            <Panel title={t("events.addEvent")}>
              <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="sm:col-span-2">
                  <label htmlFor="event-name" className="block text-xs font-medium text-gray-400 mb-1">
                    {t("events.name")} *
                  </label>
                  <input
                    id="event-name"
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => updateField("name", e.target.value)}
                    className="w-full px-3 py-2 text-sm bg-gray-800/50 border border-gray-700/50 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-ocean-500/50 focus:ring-1 focus:ring-ocean-500/30"
                    placeholder={t("events.name")}
                  />
                </div>
                <div className="sm:col-span-2">
                  <label htmlFor="event-description" className="block text-xs font-medium text-gray-400 mb-1">
                    {t("events.description")}
                  </label>
                  <input
                    id="event-description"
                    type="text"
                    value={formData.description}
                    onChange={(e) => updateField("description", e.target.value)}
                    className="w-full px-3 py-2 text-sm bg-gray-800/50 border border-gray-700/50 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-ocean-500/50 focus:ring-1 focus:ring-ocean-500/30"
                    placeholder={t("events.description")}
                  />
                </div>
                <div>
                  <label htmlFor="event-category" className="block text-xs font-medium text-gray-400 mb-1">
                    {t("events.category")}
                  </label>
                  <select
                    id="event-category"
                    value={formData.category}
                    onChange={(e) => updateField("category", e.target.value)}
                    className="w-full px-3 py-2 text-sm bg-gray-800/50 border border-gray-700/50 rounded-lg text-white focus:outline-none focus:border-ocean-500/50 focus:ring-1 focus:ring-ocean-500/30"
                  >
                    {categories.map((cat) => (
                      <option key={cat} value={cat}>
                        {t(`events.${cat}`)}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="event-location" className="block text-xs font-medium text-gray-400 mb-1">
                    {t("events.location")}
                  </label>
                  <input
                    id="event-location"
                    type="text"
                    value={formData.location}
                    onChange={(e) => updateField("location", e.target.value)}
                    className="w-full px-3 py-2 text-sm bg-gray-800/50 border border-gray-700/50 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-ocean-500/50 focus:ring-1 focus:ring-ocean-500/30"
                    placeholder={t("events.location")}
                  />
                </div>
                <div>
                  <label htmlFor="event-start-date" className="block text-xs font-medium text-gray-400 mb-1">
                    {t("events.startDate")} *
                  </label>
                  <input
                    id="event-start-date"
                    type="date"
                    required
                    value={formData.start_date}
                    onChange={(e) => updateField("start_date", e.target.value)}
                    className="w-full px-3 py-2 text-sm bg-gray-800/50 border border-gray-700/50 rounded-lg text-white focus:outline-none focus:border-ocean-500/50 focus:ring-1 focus:ring-ocean-500/30"
                  />
                </div>
                <div>
                  <label htmlFor="event-end-date" className="block text-xs font-medium text-gray-400 mb-1">
                    {t("events.endDate")}
                  </label>
                  <input
                    id="event-end-date"
                    type="date"
                    value={formData.end_date}
                    onChange={(e) => updateField("end_date", e.target.value)}
                    className="w-full px-3 py-2 text-sm bg-gray-800/50 border border-gray-700/50 rounded-lg text-white focus:outline-none focus:border-ocean-500/50 focus:ring-1 focus:ring-ocean-500/30"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label htmlFor="event-impact" className="block text-xs font-medium text-gray-400 mb-1">
                    {t("events.impact")}
                  </label>
                  <input
                    id="event-impact"
                    type="text"
                    value={formData.impact_estimate}
                    onChange={(e) => updateField("impact_estimate", e.target.value)}
                    className="w-full px-3 py-2 text-sm bg-gray-800/50 border border-gray-700/50 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-ocean-500/50 focus:ring-1 focus:ring-ocean-500/30"
                    placeholder={t("events.impact")}
                  />
                </div>
                <div className="sm:col-span-2 flex items-center gap-3 justify-end">
                  <button
                    type="button"
                    onClick={() => {
                      setShowForm(false);
                      setFormData(EMPTY_FORM);
                    }}
                    className="px-4 py-2 text-sm font-medium rounded-lg text-gray-400 hover:text-white hover:bg-gray-800/50 transition-colors"
                  >
                    {t("events.cancel")}
                  </button>
                  <button
                    type="submit"
                    disabled={submitting || !formData.name || !formData.start_date}
                    className="px-4 py-2 text-sm font-medium rounded-lg bg-ocean-500 text-white hover:bg-ocean-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {submitting ? t("common.loading") : t("events.save")}
                  </button>
                </div>
              </form>
            </Panel>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Category Filter Pills */}
      <motion.div variants={fadeUp} className="flex items-center gap-2 flex-wrap" role="group" aria-label={t("events.category")}>
        <button
          onClick={() => setSelectedCategory(null)}
          className={`px-3 py-1.5 text-xs font-medium rounded-full border transition-colors ${
            selectedCategory === null
              ? "bg-ocean-500/20 text-ocean-400 border-ocean-500/40"
              : "text-gray-400 border-gray-700/50 hover:text-white hover:border-gray-600/50"
          }`}
          aria-pressed={selectedCategory === null}
        >
          {t("events.allCategories")}
        </button>
        {categories.map((cat) => {
          const style = getCategoryStyle(cat);
          const isActive = selectedCategory === cat;
          return (
            <button
              key={cat}
              onClick={() => setSelectedCategory(isActive ? null : cat)}
              className={`px-3 py-1.5 text-xs font-medium rounded-full border transition-colors ${
                isActive
                  ? `${style.bg} ${style.text} ${style.border}`
                  : "text-gray-400 border-gray-700/50 hover:text-white hover:border-gray-600/50"
              }`}
              aria-pressed={isActive}
            >
              {t(`events.${cat}`)}
            </button>
          );
        })}
      </motion.div>

      {/* Events Timeline */}
      <motion.div variants={fadeUp}>
        {eventsError ? (
          <Panel>
            <ErrorState message={t("common.errorLoading")} onRetry={refetchEvents} />
          </Panel>
        ) : eventsLoading ? (
          <Panel>
            <div className="flex items-center justify-center py-12" role="status" aria-live="polite">
              <div className="flex flex-col items-center gap-3">
                <div className="w-8 h-8 border-2 border-ocean-500 border-t-transparent rounded-full animate-spin" />
                <span className="text-sm text-gray-400">{t("common.loading")}</span>
              </div>
            </div>
          </Panel>
        ) : groupedEvents.size === 0 ? (
          <Panel>
            <div className="flex items-center justify-center py-12">
              <p className="text-sm text-gray-500">{t("events.noEvents")}</p>
            </div>
          </Panel>
        ) : (
          <div className="space-y-6">
            {Array.from(groupedEvents.entries()).map(([monthKey, events]) => (
              <Panel key={monthKey}>
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
                    {formatMonthLabel(monthKey)}
                  </h3>
                </div>
                <div className="space-y-3">
                  {events.map((event) => (
                    <EventCard
                      key={event.id}
                      event={event}
                      onDelete={handleDelete}
                      t={t}
                      isExpanded={expandedEventId === event.id}
                      onToggleExpand={() =>
                        setExpandedEventId((prev) => (prev === event.id ? null : event.id))
                      }
                    />
                  ))}
                </div>
              </Panel>
            ))}
          </div>
        )}
      </motion.div>
    </motion.div>
  );
}
