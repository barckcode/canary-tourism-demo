import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api } from "./client";

describe("fetchJSON timeout behaviour", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(async () => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("passes an AbortSignal to fetch", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: 1 }), { status: 200 }),
    );

    const promise = api.dashboard.kpis();
    await vi.runAllTimersAsync();
    await promise;

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const callArgs = fetchSpy.mock.calls[0];
    expect(callArgs[1]).toHaveProperty("signal");
    expect(callArgs[1]!.signal).toBeInstanceOf(AbortSignal);
  });

  it("throws 'Request timed out' when the timeout expires", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      (_input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          if (init?.signal) {
            init.signal.addEventListener("abort", () => {
              reject(new DOMException("The operation was aborted.", "AbortError"));
            });
          }
        }),
    );

    // Attach a catch handler immediately to prevent unhandled rejection
    const promise = api.dashboard.kpis();
    const caughtPromise = promise.catch((err: Error) => err);

    // Advance past the default 15s timeout
    await vi.advanceTimersByTimeAsync(15_000);

    const error = await caughtPromise;
    expect(error).toBeInstanceOf(Error);
    expect((error as Error).message).toBe("Request timed out");
  });

  it("clears the timer when the request succeeds", async () => {
    const clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout");

    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ result: "ok" }), { status: 200 }),
    );

    const promise = api.dashboard.kpis();
    await vi.runAllTimersAsync();
    await promise;

    // clearTimeout should have been called (in the finally block)
    expect(clearTimeoutSpy).toHaveBeenCalled();
  });
});
