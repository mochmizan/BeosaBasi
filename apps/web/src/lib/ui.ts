// Utilitas UI — label status, tahap pemrosesan, pemformat waktu,
// pembacaan durasi berkas lokal, dan penyusun ekspor lokal.

export type Tone = "coral" | "violet" | "mint" | "amber" | "slate";

export interface StatusMeta {
  label: string;
  tone: Tone;
  note: string;
}

export const STATUS: Record<string, StatusMeta> = {
  queued: { label: "Menunggu", tone: "amber", note: "Job menunggu pekerja transkripsi." },
  processing: { label: "Diproses", tone: "violet", note: "Audio sedang ditranskripsi." },
  completed: { label: "Selesai", tone: "mint", note: "Transkrip siap dibaca dan diedit." },
  failed: { label: "Gagal", tone: "coral", note: "Job gagal diproses." },
  expired: { label: "Kedaluwarsa", tone: "slate", note: "Job kedaluwarsa sebelum diproses." },
  cancelled: { label: "Dibatalkan", tone: "slate", note: "Job dibatalkan oleh pengguna." },
};

export const STAGE: Record<string, { label: string; short: string }> = {
  probing: { label: "Memeriksa audio", short: "Periksa" },
  transcribing: { label: "Mentranskripsi", short: "Transkripsi" },
  diarizing: { label: "Melabeli pembicara", short: "Pembicara" },
  merging: { label: "Merapikan transkrip", short: "Rapikan" },
};

export const STAGE_ORDER = ["probing", "transcribing", "diarizing", "merging"] as const;

export const TONES: Tone[] = ["coral", "violet", "mint", "amber", "slate"];

export function toneOf(index: number): Tone {
  return TONES[index % TONES.length];
}

export function parseDuration(value: string | number | null | undefined): number {
  if (value === null || value === undefined || value === "" || value === "—") return 0;
  if (typeof value === "number") return value;
  const parts = String(value).split(":").map(Number);
  if (parts.some(Number.isNaN)) return 0;
  return parts.reduce((acc, part) => acc * 60 + part, 0);
}

export function formatClock(total: number | null | undefined): string {
  const secs = Math.max(0, Math.round(total ?? 0));
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function stamp(total: number, separator: string): string {
  const wholeMs = Math.max(0, Math.round((total ?? 0) * 1000));
  const h = String(Math.floor(wholeMs / 3600000)).padStart(2, "0");
  const m = String(Math.floor((wholeMs % 3600000) / 60000)).padStart(2, "0");
  const s = String(Math.floor((wholeMs % 60000) / 1000)).padStart(2, "0");
  const ms = String(wholeMs % 1000).padStart(3, "0");
  return `${h}:${m}:${s}${separator}${ms}`;
}

export interface UiSegment {
  speaker: string;
  role: string;
  start: number;
  end: number;
  time: string;
  text: string;
  confidence: number;
  edited: boolean;
}

export interface UiSpeaker {
  name: string;
  role: string;
  original: string;
  tone: Tone;
}

export interface UiJobBase {
  id: string;
  title: string;
  file: string;
  format: string;
  sizeMb: number;
  status: string;
  duration: string;
  seconds: number;
  language: string;
  diarized: boolean;
  date: string;
  speakers?: UiSpeaker[];
}

export function buildTXT(
  job: UiJobBase,
  segments: UiSegment[],
  includeSpeaker = true,
): string {
  const header = `${job.title}\n${job.file} · ${job.duration} · ${job.language}\n\n`;
  const body = segments
    .map((s) => {
      const spk =
        includeSpeaker && s.speaker
          ? ` ${s.speaker}${s.role ? ` (${s.role})` : ""}\n`
          : " ";
      return `[${s.time}]${spk}${s.text}`;
    })
    .join("\n\n");
  return header + body;
}

export function buildSRT(segments: UiSegment[], includeSpeaker = true): string {
  return segments
    .map((s, i) => {
      const start = s.start || 0;
      const end = s.end || (segments[i + 1]?.start ?? start + 6);
      const prefix = includeSpeaker && s.speaker ? `${s.speaker}: ` : "";
      return `${i + 1}\n${stamp(start, ",")} --> ${stamp(Math.max(end, start + 0.5), ",")}\n${prefix}${s.text}\n`;
    })
    .join("\n");
}

export function buildVTT(segments: UiSegment[], includeSpeaker = true): string {
  const cues = segments
    .map((s, i) => {
      const start = s.start || 0;
      const end = s.end || (segments[i + 1]?.start ?? start + 6);
      const prefix = includeSpeaker && s.speaker ? `<v ${s.speaker}>` : "";
      return `${stamp(start, ".")} --> ${stamp(Math.max(end, start + 0.5), ".")}\n${prefix}${s.text}\n`;
    })
    .join("\n");
  return `WEBVTT\n\n${cues}`;
}

export function fileBase(job: UiJobBase): string {
  return (job.file || job.title || "transkrip")
    .replace(/\.[a-z0-9]+$/i, "")
    .replace(/[^\w\s-]/g, "")
    .trim();
}

export function downloadText(filename: string, text: string, mime = "text/plain;charset=utf-8"): void {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function countWords(segments: UiSegment[]): number {
  return segments.reduce(
    (acc, s) => acc + s.text.split(/\s+/).filter(Boolean).length,
    0,
  );
}

/** Label bahasa UI dari kode kontrak. */
export function languageLabel(code: string): string {
  if (code === "id") return "Bahasa Indonesia";
  if (code === "en") return "English";
  if (code === "auto") return "Deteksi otomatis";
  return code;
}

/** Tanggal relatif sederhana untuk daftar job. */
export function relativeDate(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return iso;
  const diff = Date.now() - then;
  const minutes = Math.round(diff / 60000);
  if (minutes < 1) return "Baru saja";
  if (minutes < 60) return `${minutes} menit lalu`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} jam lalu`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days} hari lalu`;
  return new Intl.DateTimeFormat("id-ID", { day: "numeric", month: "short" }).format(
    new Date(then),
  );
}

/** Baca durasi audio di browser sebagai petunjuk kuota & batas 90 menit (TK-042). */
export function probeAudioDuration(file: File): Promise<number | null> {
  if (typeof document === "undefined" || typeof URL === "undefined") {
    return Promise.resolve(null);
  }
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const audio = document.createElement("audio");
    audio.preload = "metadata";
    let settled = false;
    const finish = (val: number | null) => {
      if (settled) return;
      settled = true;
      URL.revokeObjectURL(url);
      audio.removeAttribute("src");
      resolve(val);
    };
    const timer = setTimeout(() => finish(null), 3500);
    audio.onloadedmetadata = () => {
      clearTimeout(timer);
      const dur = audio.duration;
      if (Number.isFinite(dur) && dur > 0) finish(dur);
      else finish(null);
    };
    audio.onerror = () => {
      clearTimeout(timer);
      finish(null);
    };
    audio.src = url;
  });
}
