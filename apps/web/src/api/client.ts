// Klien API terketik dari contracts/openapi.yaml (TK-040).
// Tipe respons diimpor dari src/api-types.ts (GENERATED, jangan sunting manual).
// Semua endpoint pengguna memakai cookie sesi (`credentials: "include"`).

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

/** Unduhan mentah (ekspor TXT/SRT/VTT/DOCX). */
async function requestFile(path: string): Promise<Blob> {
  let res: Response;
  try {
    res = await fetch(`${getApiBaseUrl()}${path}`, { credentials: "include" });
  } catch {
    throw new ApiError(0, PESAN_JARINGAN);
  }
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

/** PUT satu potongan ke penyimpanan bertanda tangan (tanpa cookie). */
export function putPart(
  url: string,
  blob: Blob,
  onProgress?: (percent: number) => void,
): Promise<string> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress((e.loaded / e.total) * 100);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.getResponseHeader("ETag") ?? xhr.getResponseHeader("etag") ?? "");
      } else {
        reject(new ApiError(xhr.status, pesanUntukStatus(xhr.status)));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, PESAN_JARINGAN));
    xhr.send(blob);
  });
}

export const api = {
  getHealth(): Promise<Health> {
    return request<Health>("/healthz");
  },
  getMe(): Promise<Me> {
    return request<Me>("/api/me");
  },
  deleteMe(): Promise<Accepted> {
    return request<Accepted>("/api/me", { method: "DELETE" });
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
  signPart(uploadId: string, body: PartSignRequest): Promise<PartSignResponse> {
    return request<PartSignResponse>(
      `/api/uploads/${encodeURIComponent(uploadId)}/parts`,
      { method: "POST", body: JSON.stringify(body) },
    );
  },
  listUploadedParts(uploadId: string): Promise<UploadStatus> {
    return request<UploadStatus>(`/api/uploads/${encodeURIComponent(uploadId)}`);
  },
  completeUpload(uploadId: string, body: UploadComplete): Promise<Job> {
    return request<Job>(`/api/uploads/${encodeURIComponent(uploadId)}/complete`, {
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
