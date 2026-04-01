const BASE_URL = "/api";
const DEFAULT_TIMEOUT_MS = 15_000;

async function fetchJSON<T>(
  path: string,
  options?: RequestInit & { timeout?: number },
): Promise<T> {
  const { timeout = DEFAULT_TIMEOUT_MS, signal: externalSignal, ...fetchOptions } = options ?? {};
  const timeoutController = new AbortController();
  const timer = setTimeout(() => timeoutController.abort(), timeout);

  // If the caller provided an external signal (e.g. from AbortController in useQuery),
  // abort the timeout controller when the external signal fires so fetch is cancelled.
  if (externalSignal) {
    if (externalSignal.aborted) {
      clearTimeout(timer);
      throw new DOMException("The operation was aborted.", "AbortError");
    }
    externalSignal.addEventListener("abort", () => timeoutController.abort(), { once: true });
  }

  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...fetchOptions,
      signal: timeoutController.signal,
    });
    if (!res.ok) {
      throw new Error(`API error: ${res.status} ${res.statusText}`);
    }
    return await res.json();
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      // Re-throw as AbortError if it came from the external signal so callers can
      // distinguish cancellation from timeout.
      if (externalSignal?.aborted) {
        throw err;
      }
      throw new Error("Request timed out");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

/** Options bag accepted by every API method so callers (e.g. useQuery) can
 *  forward an AbortSignal for proper request cancellation. */
export interface ApiCallOptions {
  signal?: AbortSignal;
}

export const api = {
  dashboard: {
    kpis: (opts?: ApiCallOptions) => fetchJSON("/dashboard/kpis", { signal: opts?.signal }),
    summary: (opts?: ApiCallOptions) => fetchJSON("/dashboard/summary", { signal: opts?.signal }),
    topMarkets: (opts?: ApiCallOptions) => fetchJSON("/dashboard/top-markets", { signal: opts?.signal }),
    seasonalPosition: (opts?: ApiCallOptions) => fetchJSON("/dashboard/seasonal-position", { signal: opts?.signal }),
    mapData: (period?: string, opts?: ApiCallOptions) => {
      const params = period ? `?period=${period}` : "";
      return fetchJSON(`/dashboard/map${params}`, { signal: opts?.signal });
    },
  },
  timeseries: {
    get: (params: Record<string, string>, opts?: ApiCallOptions) => {
      const qs = new URLSearchParams(params).toString();
      return fetchJSON(`/timeseries?${qs}`, { signal: opts?.signal });
    },
    indicators: (opts?: ApiCallOptions) => fetchJSON("/timeseries/indicators", { signal: opts?.signal }),
    yoy: (params?: Record<string, string>, opts?: ApiCallOptions) => {
      const qs = params ? new URLSearchParams(params).toString() : "";
      return fetchJSON(`/timeseries/yoy${qs ? `?${qs}` : ""}`, { signal: opts?.signal });
    },
  },
  predictions: {
    get: (params?: Record<string, string>, opts?: ApiCallOptions) => {
      const qs = params ? new URLSearchParams(params).toString() : "";
      return fetchJSON(`/predictions?${qs}`, { signal: opts?.signal });
    },
    compare: (params?: Record<string, string>, opts?: ApiCallOptions) => {
      const qs = params ? new URLSearchParams(params).toString() : "";
      return fetchJSON(`/predictions/compare?${qs}`, { signal: opts?.signal });
    },
    trainingInfo: (opts?: ApiCallOptions) => fetchJSON("/predictions/training-info", { signal: opts?.signal }),
  },
  profiles: {
    list: (opts?: ApiCallOptions) => fetchJSON("/profiles", { signal: opts?.signal }),
    detail: (id: number, opts?: ApiCallOptions) => fetchJSON(`/profiles/${id}`, { signal: opts?.signal }),
    nationalities: (opts?: ApiCallOptions) => fetchJSON("/profiles/nationalities", { signal: opts?.signal }),
    flows: (opts?: ApiCallOptions) => fetchJSON("/profiles/flows", { signal: opts?.signal }),
    spending: (opts?: ApiCallOptions) => fetchJSON("/profiles/spending", { signal: opts?.signal }),
    nationalityTrends: (params?: Record<string, string>, opts?: ApiCallOptions) => {
      const qs = params ? new URLSearchParams(params).toString() : "";
      return fetchJSON(`/profiles/nationality-trends${qs ? `?${qs}` : ""}`, { signal: opts?.signal });
    },
  },
  events: {
    list: (params?: Record<string, string>, opts?: ApiCallOptions) => {
      const qs = params ? new URLSearchParams(params).toString() : "";
      return fetchJSON(`/events${qs ? `?${qs}` : ""}`, { signal: opts?.signal });
    },
    categories: (opts?: ApiCallOptions) => fetchJSON("/events/categories", { signal: opts?.signal }),
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
    impact: (eventId: number, opts?: ApiCallOptions) =>
      fetchJSON(`/events/${eventId}/impact`, { signal: opts?.signal }),
  },
  comparison: {
    provinces: (indicator?: string, periods?: number, opts?: ApiCallOptions) => {
      const params = new URLSearchParams();
      if (indicator) params.set("indicator", indicator);
      if (periods) params.set("periods", String(periods));
      return fetchJSON(`/comparison/provinces?${params}`, { signal: opts?.signal });
    },
    accommodationTypes: (indicator?: string, periods?: number, opts?: ApiCallOptions) => {
      const params = new URLSearchParams();
      if (indicator) params.set("indicator", indicator);
      if (periods) params.set("periods", String(periods));
      return fetchJSON(`/comparison/accommodation-types?${params}`, { signal: opts?.signal });
    },
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
    list: (opts?: ApiCallOptions) => fetchJSON("/scenarios/saved", { signal: opts?.signal }),
    get: (id: number, opts?: ApiCallOptions) => fetchJSON(`/scenarios/saved/${id}`, { signal: opts?.signal }),
    delete: (id: number) =>
      fetchJSON(`/scenarios/saved/${id}`, { method: "DELETE" }),
    compare: (ids: number[]) =>
      fetchJSON("/scenarios/compare", {
        method: "POST",
        body: JSON.stringify(ids),
      }),
    featureImportance: (opts?: ApiCallOptions) => fetchJSON("/scenarios/feature-importance", { signal: opts?.signal }),
  },
};
