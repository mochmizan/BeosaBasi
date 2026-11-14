import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, getApiBaseUrl } from "./client";
import { PESAN_GALAT } from "./errors";

afterEach(() => {
  vi.unstubAllGlobals();
});

function mockFetch(res: { body?: unknown; status?: number; ok?: boolean }): void {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: res.ok ?? true,
      status: res.status ?? 200,
      json: () => Promise.resolve(res.body ?? {}),
    } as unknown as Response),
  );
}

describe("api client", () => {
  it("basis URL default ke mock Prism :4010", () => {
    expect(getApiBaseUrl()).toContain("4010");
  });

  it("getHealth memakai /healthz", async () => {
    mockFetch({ body: { status: "ok" } });
    const h = await api.getHealth();
    expect(h.status).toBe("ok");
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/healthz"),
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("memetakan badan galat kontrak ke ApiError Indonesia", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: () =>
          Promise.resolve({ code: "QUOTA_EXCEEDED", message: "" }),
      }),
    );
    await expect(api.listJobs()).rejects.toMatchObject({
      status: 403,
      message: PESAN_GALAT.QUOTA_EXCEEDED,
    } satisfies Partial<ApiError>);
  });

  it("galat jaringan menjadi pesan koneksi", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("down")),
    );
    await expect(api.getHealth()).rejects.toMatchObject({ status: 0 });
  });
});
