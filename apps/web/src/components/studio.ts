// Konteks bersama seluruh aplikasi (tema, kuota, job, unggahan, rekaman suara, preferensi).
// Tanpa akun & tanpa modal kebijakan (sesuai ADR-0001).
// Penyedia hidup di Layout.tsx; halaman memakai useStudio().

import { createContext, useContext } from "react";
import type { JobSummary, Me } from "../api-types";

export interface UploadFileMeta {
  name: string;
  sizeMb: number;
  durationSec?: number;
  diarized: boolean;
  speakers: number;
  language: "id" | "en" | "auto";
  source?: "upload" | "record";
}

export type UploadPhase =
  | "idle"
  | "uploading"
  | "queued"
  | "processing"
  | "completed"
  | "failed";

export interface UploadState {
  phase: UploadPhase;
  progress: number;
  partsDone?: number;
  partsTotal?: number;
  fileMeta: UploadFileMeta | null;
  stage: string | null;
  jobId: string | null;
  queuePosition?: number | null;
  eta?: string | null;
  canResume?: boolean;
  error: string | null;
}

export interface QuotaView {
  minutes: number;
  used: number;
  maxActive: number;
  active: number;
  reset: string;
}

export interface StudioPrefs {
  defaultLanguage: "id" | "en" | "auto";
  defaultDiarization: boolean;
  defaultSpeakers: number;
  defaultExportFormat: "txt" | "srt" | "vtt" | "docx";
  includeSpeakerLabels: boolean;
}

export type InputMode = "upload" | "record";

export interface Studio {
  theme: "dark" | "light";
  toggleTheme: () => void;

  view: string;
  navigate: (view: "home" | "library" | "insights" | "settings") => void;
  goJob: (id: string) => void;

  inputMode: InputMode;
  setInputMode: (mode: InputMode) => void;
  startNewUpload: () => void;
  startNewRecording: () => void;

  me: Me | null;
  quota: QuotaView;

  prefs: StudioPrefs;
  updatePrefs: (patch: Partial<StudioPrefs>) => void;

  jobs: JobSummary[];
  refreshData: () => void;

  workerOnline: boolean;
  refreshHealth: () => void;

  upload: UploadState;
  startUpload: (file: File, meta: UploadFileMeta) => void;
  resumeUpload: () => void;
  cancelUpload: (force?: boolean) => void;

  query: string;
  setQuery: (value: string) => void;
  searchResults: UiJobLite[];

  activeId: string | null;
  selectJob: (id: string, title: string) => void;

  toast: (message: string) => void;
}

/** Kartu ringkas untuk hasil pencarian. */
export interface UiJobLite {
  id: string;
  title: string;
  file: string;
  format: string;
  duration: string;
  status: string;
}

export const StudioContext = createContext<Studio | null>(null);

export function useStudio(): Studio {
  const ctx = useContext(StudioContext);
  if (ctx === null) throw new Error("useStudio harus dipakai di dalam Layout.");
  return ctx;
}

export const IDLE_UPLOAD: UploadState = {
  phase: "idle",
  progress: 0,
  partsDone: 0,
  partsTotal: 0,
  fileMeta: null,
  stage: null,
  jobId: null,
  queuePosition: null,
  eta: null,
  canResume: false,
  error: null,
};

export const DEFAULT_PREFS: StudioPrefs = {
  defaultLanguage: "id",
  defaultDiarization: false,
  defaultSpeakers: 2,
  defaultExportFormat: "txt",
  includeSpeakerLabels: true,
};

export const DAILY_MINUTES = 60;
export const MAX_ACTIVE = 2;
