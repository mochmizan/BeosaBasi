// Klien API terketik dari contracts/openapi.yaml (TK-040, TK-042).
// Tipe respons diimpor dari src/api-types.ts (GENERATED, jangan sunting manual).
// Mendukung cookie sesi (`credentials: "include"`) + header fallback
// `X-Session-Token` agar tunnel lintas-domain (trycloudflare.com) dan
// peramban seluler tetap menjaga sesi anonim tanpa login.

import type {
  Accepted,
  AudioUrl,
  ConsentGive,
  Consent,
  Health,
  Job,
  JobDetail,
  JobList,
  KodeGalat,
  Me,
  PartSignRequest,
  PartSignResponse,
  Segment,
  SegmentPatch,
  Speaker,
  SpeakerRename,
  Transcript,
  UploadComplete,
  UploadInit,
  UploadSession,
  UploadStatus,
} from "../api-types";
import {
  ApiError,
  PESAN_JARINGAN,
  pesanUntukKode,
  pesanUntukStatus,
} from "./errors";

export { ApiError };

const SESSION_STORAGE_KEY = "beosabasi_session_token";

/** Cadangan memori bila localStorage tak ada (vitest/node) atau diblokir. */
let tokenMemori: string | null = null;

export function getSessionToken(): string | null {
  if (tokenMemori) return tokenMemori;
  try {
    return typeof localStorage !== "undefined"
      ? localStorage.getItem(SESSION_STORAGE_KEY)
      : null;
  } catch {
    return null;
  }
}

export function setSessionToken(token: string | null): void {
  const bersih = token && token.trim() !== "" ? token.trim() : null;
  tokenMemori = bersih;
  try {
    if (typeof localStorage === "undefined") return;
    if (bersih) {
      localStorage.setItem(SESSION_STORAGE_KEY, bersih);
    } else {
      localStorage.removeItem(SESSION_STORAGE_KEY);
    }
  } catch {
    // Abaikan bila localStorage diblokir mode privat.
  }
}

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

function captureSessionHeader(res: Response): void {
  try {
    const token = res.headers?.get?.("X-Session-Token") ?? res.headers?.get?.("x-session-token");
    if (token) setSessionToken(token);
  } catch {
    // Mock Response pada unit test mungkin tidak menyertakan headers.
  }
}

function buildHeaders(extra?: HeadersInit, json = true): Record<string, string> {
  const headers: Record<string, string> = {};
  if (json) headers["Content-Type"] = "application/json";
  const token = getSessionToken();
  if (token) headers["X-Session-Token"] = token;
  if (extra) {
    if (extra instanceof Headers) {
      extra.forEach((v, k) => {
        headers[k] = v;
      });
    } else if (Array.isArray(extra)) {
      for (const [k, v] of extra) headers[k] = v;
    } else {
      Object.assign(headers, extra);
    }
  }
  return headers;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${getApiBaseUrl()}${path}`, {
      credentials: "include",
      ...init,
      headers: buildHeaders(init?.headers, true),
    });
  } catch {
    throw new ApiError(0, PESAN_JARINGAN);
  }
  captureSessionHeader(res);
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

/** Unduhan mentah (ekspor TXT/SRT/VTT/DOCX). */
async function requestFile(path: string): Promise<Blob> {
  let res: Response;
  try {
    res = await fetch(`${getApiBaseUrl()}${path}`, {
      credentials: "include",
      headers: buildHeaders(undefined, false),
    });
  } catch {
    throw new ApiError(0, PESAN_JARINGAN);
  }
  captureSessionHeader(res);
  if (!res.ok) {
    let code: KodeGalat | undefined;
    try {
      const body = (await res.json()) as BadanGalat;
      if (kodeValid(body.code)) code = body.code;
    } catch {
      code = undefined;
    }
    throw new ApiError(res.status, pesanUntukStatus(res.status), code);
  }
  return res.blob();
}

/** Kirim satu potongan lewat relay API (same-origin, tanpa preflight CORS).
 * Presigned URL (signPart) dicadangkan untuk R2 + CORS bucket (TK-003). */
export function putPart(
  jobId: string,
  partNumber: number,
  blob: Blob,
  onProgress?: (loadedBytes: number) => void,
  signal?: AbortSignal,
): Promise<string> {
  return (async () => {
    if (signal?.aborted) {
      throw new ApiError(0, "Unggahan dibatalkan.");
    }
    let res: Response;
    try {
      res = await fetch(
        `${getApiBaseUrl()}/api/uploads/${encodeURIComponent(jobId)}/parts/${partNumber}`,
        {
          method: "PUT",
          credentials: "include",
          headers: buildHeaders(undefined, false),
          body: blob,
          signal,
        },
      );
    } catch {
      throw new ApiError(0, PESAN_JARINGAN);
    }
    captureSessionHeader(res);
    if (!res.ok) {
      let code: KodeGalat | undefined;
      try {
        const body = (await res.json()) as BadanGalat;
        if (kodeValid(body.code)) code = body.code;
      } catch {
        code = undefined;
      }
      throw new ApiError(
        res.status,
        code !== undefined ? pesanUntukKode(code) : pesanUntukStatus(res.status),
        code,
      );
    }
    const body = (await res.json()) as { etag?: unknown };
    const etag = typeof body.etag === "string" ? body.etag : "";
    onProgress?.(blob.size);
    return etag;
  })();
}

export const api = {
  getHealth(): Promise<Health> {
    return request<Health>("/healthz");
  },
  getMe(): Promise<Me> {
    return request<Me>("/api/me");
  },
  async deleteMe(): Promise<Accepted> {
    const res = await request<Accepted>("/api/me", { method: "DELETE" });
    setSessionToken(null);
    return res;
  },
  giveConsent(body: ConsentGive): Promise<Consent> {
    return request<Consent>("/api/consents", { method: "POST", body: JSON.stringify(body) });
  },
  withdrawConsent(): Promise<Accepted> {
    return request<Accepted>("/api/consents", { method: "DELETE" });
  },
  initUpload(body: UploadInit): Promise<UploadSession> {
    return request<UploadSession>("/api/uploads", { method: "POST", body: JSON.stringify(body) });
  },
  signPart(jobId: string, body: PartSignRequest): Promise<PartSignResponse> {
    return request<PartSignResponse>(
      `/api/uploads/${encodeURIComponent(jobId)}/parts`,
      { method: "POST", body: JSON.stringify(body) },
    );
  },
  listUploadedParts(jobId: string): Promise<UploadStatus> {
    return request<UploadStatus>(`/api/uploads/${encodeURIComponent(jobId)}`);
  },
  completeUpload(jobId: string, body: UploadComplete): Promise<Job> {
    return request<Job>(`/api/uploads/${encodeURIComponent(jobId)}/complete`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
  listJobs(): Promise<JobList> {
    return request<JobList>("/api/jobs");
  },
  getJob(id: string): Promise<JobDetail> {
    return request<JobDetail>(`/api/jobs/${encodeURIComponent(id)}`);
  },
  deleteJob(id: string): Promise<Accepted> {
    return request<Accepted>(`/api/jobs/${encodeURIComponent(id)}`, { method: "DELETE" });
  },
  getTranscript(id: string): Promise<Transcript> {
    return request<Transcript>(`/api/jobs/${encodeURIComponent(id)}/transcript`);
  },
  patchSegment(jobId: string, n: number, body: SegmentPatch): Promise<Segment> {
    return request<Segment>(
      `/api/jobs/${encodeURIComponent(jobId)}/segments/${n}`,
      { method: "PATCH", body: JSON.stringify(body) },
    );
  },
  renameSpeaker(jobId: string, sid: string, body: SpeakerRename): Promise<Speaker> {
    return request<Speaker>(
      `/api/jobs/${encodeURIComponent(jobId)}/speakers/${encodeURIComponent(sid)}`,
      { method: "PATCH", body: JSON.stringify(body) },
    );
  },
  getAudioUrl(id: string): Promise<AudioUrl> {
    return request<AudioUrl>(`/api/jobs/${encodeURIComponent(id)}/audio-url`);
  },
  async exportTranscript(id: string, format: "txt" | "srt" | "vtt" | "docx"): Promise<Blob> {
    return requestFile(
      `/api/jobs/${encodeURIComponent(id)}/export?format=${encodeURIComponent(format)}`,
    );
  },
};

/** Opsi unggah multipart paralel (3x potongan 8 MiB + dukungan pelanjutan ListParts). */
export interface MultipartUploadOptions {
  file: File;
  language: "id" | "en" | "auto";
  diarization: boolean;
  speakers?: number;
  concurrency?: number;
  existingSession?: UploadSession | null;
  knownEtags?: Map<number, string>;
  signal?: AbortSignal;
  onSession?: (session: UploadSession, etags: Map<number, string>) => void;
  onProgress?: (percent: number, partsDone: number, partsTotal: number) => void;
}

export async function uploadFileMultipart(opts: MultipartUploadOptions): Promise<Job> {
  const {
    file,
    language,
    diarization,
    speakers,
    concurrency = 3,
    existingSession,
    knownEtags,
    signal,
    onSession,
    onProgress,
  } = opts;

  const rawType = (file.type || "").split(";", 1)[0].trim().toLowerCase();
  const ext = (file.name.split(".").pop() || "").toLowerCase();
  const fallbackMime: Record<string, string> = {
    mp3: "audio/mpeg",
    m4a: "audio/mp4",
    wav: "audio/wav",
    flac: "audio/flac",
    ogg: "audio/ogg",
    opus: "audio/opus",
    mp4: "video/mp4",
    webm: "audio/webm",
  };
  const contentType = rawType || fallbackMime[ext] || "audio/webm";

  const session =
    existingSession ??
    (await api.initUpload({
      filename: file.name,
      size_bytes: file.size,
      content_type: contentType,
      language,
      diarization,
      min_speakers: diarization ? speakers : undefined,
      max_speakers: diarization ? speakers : undefined,
      turnstile_token: "stub",
    }));

  const etags = new Map<number, string>(knownEtags ? Array.from(knownEtags.entries()) : []);
  onSession?.(session, etags);

  // Bila melanjutkan sesi yang terputus, periksa potongan yang sudah tercatat di server (ListParts).
  let serverDone = new Set<number>();
  if (existingSession) {
    try {
      const status = await api.listUploadedParts(session.job_id);
      serverDone = new Set(status.parts_done.filter((n) => etags.has(n)));
    } catch {
      serverDone = new Set();
    }
  }

  const totalParts = Math.max(1, session.part_count);
  const partSize = session.part_size;
  const loadedPerPart = new Map<number, number>();

  for (let partNumber = 1; partNumber <= totalParts; partNumber += 1) {
    const start = (partNumber - 1) * partSize;
    const end = Math.min(file.size, partNumber * partSize);
    if (serverDone.has(partNumber)) {
      loadedPerPart.set(partNumber, Math.max(0, end - start));
    } else {
      loadedPerPart.set(partNumber, 0);
    }
  }

  const reportProgress = () => {
    if (!onProgress) return;
    let uploadedBytes = 0;
    loadedPerPart.forEach((b) => {
      uploadedBytes += b;
    });
    const ratio = file.size > 0 ? Math.min(1, uploadedBytes / file.size) : 1;
    onProgress(Math.round(ratio * 95), etags.size, totalParts);
  };

  reportProgress();

  const queue: number[] = [];
  for (let partNumber = 1; partNumber <= totalParts; partNumber += 1) {
    if (!serverDone.has(partNumber)) {
      queue.push(partNumber);
    }
  }

  const uploadOnePart = async (partNumber: number): Promise<void> => {
    const start = (partNumber - 1) * partSize;
    const end = Math.min(file.size, partNumber * partSize);
    const blob = file.slice(start, end);

    let lastErr: unknown = null;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      if (signal?.aborted) throw new ApiError(0, "Unggahan dibatalkan.");
      try {
        const etag = await putPart(
          session.job_id,
          partNumber,
          blob,
          (loaded) => {
            loadedPerPart.set(partNumber, loaded);
            reportProgress();
          },
          signal,
        );
        loadedPerPart.set(partNumber, blob.size);
        etags.set(partNumber, etag);
        onSession?.(session, etags);
        reportProgress();
        return;
      } catch (err) {
        lastErr = err;
        if (signal?.aborted) throw err;
      }
    }
    throw lastErr instanceof Error ? lastErr : new ApiError(0, PESAN_JARINGAN);
  };

  const workers = Array.from({ length: Math.min(concurrency, queue.length) }, async () => {
    while (queue.length > 0) {
      if (signal?.aborted) throw new ApiError(0, "Unggahan dibatalkan.");
      const next = queue.shift();
      if (next === undefined) break;
      await uploadOnePart(next);
    }
  });

  await Promise.all(workers);

  if (signal?.aborted) {
    throw new ApiError(0, "Unggahan dibatalkan.");
  }

  const parts = Array.from({ length: totalParts }, (_, idx) => {
    const partNumber = idx + 1;
    return {
      part_number: partNumber,
      etag: etags.get(partNumber) ?? "",
    };
  });

  onProgress?.(98, totalParts, totalParts);
  const completedJob = await api.completeUpload(session.job_id, { parts });
  onProgress?.(100, totalParts, totalParts);
  return completedJob;
}
