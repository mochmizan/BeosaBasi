// Klien API terketik dari contracts/openapi.yaml (TK-040).
// Tipe respons diimpor dari src/api-types.ts (GENERATED, jangan sunting manual).
// Semua endpoint pengguna memakai cookie sesi (`credentials: "include"`).

import type {
  Health,
  JobDetail,
  JobList,
  KodeGalat,
  Me,
  Transcript,
} from "../api-types";
import {
  ApiError,
  PESAN_JARINGAN,
  pesanUntukKode,
  pesanUntukStatus,
} from "./errors";

export { ApiError };

interface BadanGalat {
  code?: KodeGalat;
  message?: string;
}

/** Basis URL API. Env produksi diisi Pages; dev default ke mock Prism :4010. */
export function getApiBaseUrl(): string {
  const dariEnv = import.meta.env.VITE_API_BASE_URL as string | undefined;
  const basis = (dariEnv ?? "").trim();
  if (basis !== "") return basis.replace(/\/+$/, "");
  return "http://localhost:4010";
}

function kodeValid(code: unknown): code is KodeGalat {
  return typeof code === "string" && code.length > 0;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${getApiBaseUrl()}${path}`, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError(0, PESAN_JARINGAN);
  }
  if (res.status === 204) return undefined as T;
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok) {
    const galat = (body ?? {}) as BadanGalat;
    const code = kodeValid(galat.code) ? galat.code : undefined;
    const message =
      typeof galat.message === "string" && galat.message !== ""
        ? galat.message
        : code !== undefined
          ? pesanUntukKode(code)
          : pesanUntukStatus(res.status);
    throw new ApiError(res.status, message, code);
  }
  return body as T;
}

export const api = {
  getHealth(): Promise<Health> {
    return request<Health>("/healthz");
  },
  getMe(): Promise<Me> {
    return request<Me>("/api/me");
  },
  listJobs(): Promise<JobList> {
    return request<JobList>("/api/jobs");
  },
  getJob(id: string): Promise<JobDetail> {
    return request<JobDetail>(`/api/jobs/${encodeURIComponent(id)}`);
  },
  getTranscript(id: string): Promise<Transcript> {
    return request<Transcript>(`/api/jobs/${encodeURIComponent(id)}/transcript`);
  },
};
