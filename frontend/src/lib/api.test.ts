import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch, getAuth, storeAuth, type AuthTokens } from "@/lib/api";

const user = {
  id: "user-1",
  email: "test@example.com",
  first_name: "Test",
  last_name: "User",
  full_name: "Test User",
  avatar_url: "",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function makeTokens(access: string, refresh = "refresh-token"): AuthTokens {
  return {
    access,
    refresh,
    user,
  };
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiFetch", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();

    const storage = new Map<string, string>();
    vi.stubGlobal("window", {});
    vi.stubGlobal("localStorage", {
      getItem: vi.fn((key: string) => storage.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => {
        storage.set(key, value);
      }),
      removeItem: vi.fn((key: string) => {
        storage.delete(key);
      }),
    });
  });

  it("refreshes expired access tokens and retries the original request", async () => {
    storeAuth(makeTokens("expired-access"));
    const refreshed = makeTokens("fresh-access", "fresh-refresh");
    const responseBody = { ok: true };

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Token is invalid or expired" }))
      .mockResolvedValueOnce(jsonResponse(200, refreshed))
      .mockResolvedValueOnce(jsonResponse(200, responseBody));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/dashboard/summary/")).resolves.toEqual(responseBody);

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/v1/auth/refresh/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ refresh: "refresh-token" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/api/v1/dashboard/summary/",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer fresh-access",
        }),
      }),
    );
    expect(getAuth()?.access).toBe("fresh-access");
  });

  it("does not refresh failed auth requests with a stale stored session", async () => {
    storeAuth(makeTokens("old-access"));
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { detail: "No active account found" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      apiFetch("/auth/login/", {
        method: "POST",
        body: JSON.stringify({ email: "test@example.com", password: "bad" }),
      }),
    ).rejects.toMatchObject({
      status: 401,
      message: "No active account found",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
