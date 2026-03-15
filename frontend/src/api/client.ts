const BASE_URL = "/api";

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  dashboard: {
    kpis: () => fetchJSON("/dashboard/kpis"),
    summary: () => fetchJSON("/dashboard/summary"),
    topMarkets: () => fetchJSON("/dashboard/top-markets"),
    seasonalPosition: () => fetchJSON("/dashboard/seasonal-position"),
    mapData: (period?: string) => {
      const params = period ? `?period=${period}` : "";
      return fetchJSON(`/dashboard/map${params}`);
    },
  },
  timeseries: {
    get: (params: Record<string, string>) => {
      const qs = new URLSearchParams(params).toString();
      return fetchJSON(`/timeseries?${qs}`);
    },
    indicators: () => fetchJSON("/timeseries/indicators"),
    yoy: (params?: Record<string, string>) => {
      const qs = params ? new URLSearchParams(params).toString() : "";
      return fetchJSON(`/timeseries/yoy${qs ? `?${qs}` : ""}`);
    },
  },
  predictions: {
    get: (params?: Record<string, string>) => {
      const qs = params ? new URLSearchParams(params).toString() : "";
      return fetchJSON(`/predictions?${qs}`);
    },
    compare: (params?: Record<string, string>) => {
      const qs = params ? new URLSearchParams(params).toString() : "";
      return fetchJSON(`/predictions/compare?${qs}`);
    },
    trainingInfo: () => fetchJSON("/predictions/training-info"),
  },
  profiles: {
    list: () => fetchJSON("/profiles"),
    detail: (id: number) => fetchJSON(`/profiles/${id}`),
    nationalities: () => fetchJSON("/profiles/nationalities"),
    flows: () => fetchJSON("/profiles/flows"),
    spending: () => fetchJSON("/profiles/spending"),
  },
  events: {
    list: (params?: Record<string, string>) => {
      const qs = params ? new URLSearchParams(params).toString() : "";
      return fetchJSON(`/events${qs ? `?${qs}` : ""}`);
    },
    categories: () => fetchJSON("/events/categories"),
    create: (data: {
      name: string;
      description?: string;
      category: string;
      start_date: string;
      end_date?: string;
      impact_estimate?: string;
      location?: string;
    }) =>
      fetchJSON("/events", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      fetchJSON(`/events/${id}`, { method: "DELETE" }),
  },
  scenarios: {
    run: (body: Record<string, number>) =>
      fetchJSON("/scenarios", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    save: (body: { name: string; occupancy_change_pct: number; adr_change_pct: number; foreign_ratio_change_pct: number; horizon: number }) =>
      fetchJSON("/scenarios/save", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    list: () => fetchJSON("/scenarios/saved"),
    get: (id: number) => fetchJSON(`/scenarios/saved/${id}`),
    delete: (id: number) =>
      fetchJSON(`/scenarios/saved/${id}`, { method: "DELETE" }),
    compare: (ids: number[]) =>
      fetchJSON("/scenarios/compare", {
        method: "POST",
        body: JSON.stringify({ scenario_ids: ids }),
      }),
    featureImportance: () => fetchJSON("/scenarios/feature-importance"),
  },
};
