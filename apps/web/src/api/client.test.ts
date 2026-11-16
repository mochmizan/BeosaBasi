import { afterEach, describe, expect, it, vi } from "vitest";
import {
  api,
  ApiError,
  getApiBaseUrl,
  getSessionToken,
  setSessionToken,
  uploadFileMultipart,
} from "./client";
import { PESAN_GALAT } from "./errors";

afterEach(() => {
  setSessionToken(null);
  vi.unstubAllGlobals();
});

function mockFetch(res: { body?: unknown; status?: number; ok?: boolean; headers?: Record<string, string> }): void {
  const hdrs = res.headers ?? {};
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: res.ok ?? true,
      status: res.status ?? 200,
      headers: {
        get: (name: string) => hdrs[name] ?? hdrs[name.toLowerCase()] ?? null,
      },
      json: () => Promise.resolve(res.body ?? {}),
    } as unknown as Response),
  );
}

describe("api client", () => {
  it("basis URL default ke mock Prism :4010", () => {
    expect(getApiBaseUrl()).toContain("4010");
  });

  it("getHealth memakai /healthz", async () => {
    mockFetch({ body: { status: "ok", worker_active: true } });
    const h = await api.getHealth();
    expect(h.status).toBe("ok");
    expect(h.worker_active).toBe(true);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/healthz"),
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("menyimpan dan mengirim header X-Session-Token lintas tunnel", async () => {
    mockFetch({
      body: {
        user_id: "00000000-0000-4000-8000-000000000001",
        email: "anonim@tanpa-login.invalid",
        quota_minutes_remaining: 60,
        active_jobs: 0,
        consent: null,
      },
      headers: { "X-Session-Token": "tok-anon-123" },
    });
    await api.getMe();
    expect(getSessionToken()).toBe("tok-anon-123");

    mockFetch({ body: { jobs: [], next_cursor: null } });
    await api.listJobs();
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/jobs"),
      expect.objectContaining({
        headers: expect.objectContaining({ "X-Session-Token": "tok-anon-123" }),
      }),
    );
  });

  it("uploadFileMultipart memakai job_id dan part_number berbasis 1", async () => {
    const relayCalls: { part: number; bytes: number }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        if (url.endsWith("/api/uploads")) {
          return Promise.resolve({
            ok: true,
            status: 201,
            headers: { get: () => null },
            json: () =>
              Promise.resolve({
                job_id: "job-123",
                upload_id: "s3-up-999",
                part_size: 10,
                part_count: 2,
              }),
          });
        }
        const relay = url.match(/\/api\/uploads\/job-123\/parts\/(\d+)$/);
        if (init?.method === "PUT" && relay) {
          const part = Number(relay[1]);
          const blob = init.body as Blob;
          relayCalls.push({ part, bytes: blob.size });
          return Promise.resolve({
            ok: true,
            status: 200,
            headers: { get: () => null },
            json: () => Promise.resolve({ etag: `etag-${part}` }),
          });
        }
        if (url.endsWith("/api/uploads/job-123/complete")) {
          return Promise.resolve({
            ok: true,
            status: 200,
            headers: { get: () => null },
            json: () =>
              Promise.resolve({
                job_id: "job-123",
                state: "queued",
                filename: "rekaman.webm",
                size_bytes: 16,
                language: "id",
                diarization: false,
                created_at: "2026-11-16T00:00:00Z",
              }),
          });
        }
        throw new Error(`Unexpected URL: ${url}`);
      }),
    );

    const file = new File([new Uint8Array(16)], "rekaman.webm", {
      type: "audio/webm;codecs=opus",
    });
    const job = await uploadFileMultipart({
      file,
      language: "id",
      diarization: false,
      concurrency: 3,
    });
    expect(job.job_id).toBe("job-123");
    expect(relayCalls.map((c) => c.part).sort()).toEqual([1, 2]);
    expect(relayCalls.reduce((n, c) => n + c.bytes, 0)).toBe(16);
  });

  it("memetakan badan galat kontrak ke ApiError Indonesia", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        headers: { get: () => null },
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
