// Konteks bersama seluruh aplikasi (tema, kuota, job, unggahan, consent).
// Penyedia hidup di Layout.tsx; halaman memakai useStudio().

import { createContext, useContext } from "react";
import type { JobSummary, Me } from "../api-types";

export interface UploadFileMeta {
  name: string;
  sizeMb: number;
  diarized: boolean;
  speakers: number;
  language: "id" | "en" | "auto";
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
  fileMeta: UploadFileMeta | null;
  stage: string | null;
  jobId: string | null;
  error: string | null;
}

export interface PendingUpload {
  file: File;
  meta: UploadFileMeta;
}

export interface QuotaView {
  minutes: number;
  used: number;
  maxActive: number;
  active: number;
  reset: string;
}

export interface ProfileView {
  name: string;
  email: string;
  initials: string;
  pilot: string;
}

export interface ConsentView {
  version: string;
  given: string;
}

export interface NoticeOptions {
  pending?: PendingUpload | null;
}

export interface Studio {
  theme: "dark" | "light";
  toggleTheme: () => void;

  view: string;
  navigate: (view: "home" | "library" | "insights" | "settings") => void;
  goJob: (id: string) => void;

  me: Me | null;
  profile: ProfileView;
  quota: QuotaView;
  consent: ConsentView | null;
  consentGiven: boolean;

  jobs: JobSummary[];
  refreshData: () => void;

  workerOnline: boolean;
  refreshHealth: () => void;

  upload: UploadState;
  startUpload: (file: File, meta: UploadFileMeta) => void;
  cancelUpload: (force?: boolean) => void;

  query: string;
  setQuery: (value: string) => void;
  searchResults: UiJobLite[];

  activeId: string | null;
  selectJob: (id: string, title: string) => void;

  toast: (message: string) => void;

  openNotice: (options?: NoticeOptions) => void;
  openGrant: () => void;
  onAgreeConsent: () => void;
  onWithdrawConsent: () => void;
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

export const IDLE_UPLOAD: UploadState = { phase: "idle", progress: 0, fileMeta: null, stage: null, jobId: null, error: null };

export const DAILY_MINUTES = 60;
export const MAX_ACTIVE = 2;
export const CONSENT_VERSION = "1.2";
