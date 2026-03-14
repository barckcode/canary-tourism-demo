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
  },
  profiles: {
    list: () => fetchJSON("/profiles"),
    detail: (id: number) => fetchJSON(`/profiles/${id}`),
    nationalities: () => fetchJSON("/profiles/nationalities"),
    flows: () => fetchJSON("/profiles/flows"),
    spending: () => fetchJSON("/profiles/spending"),
  },
  scenarios: {
    run: (body: Record<string, number>) =>
      fetchJSON("/scenarios", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },
};
