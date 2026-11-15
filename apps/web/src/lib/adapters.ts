// Adapter: model API (api-types.ts) → model UI (lib/ui.ts).

import type { Job, Segment, Speaker, Transcript } from "../api-types";
import {
  STATUS,
  formatClock,
  languageLabel,
  relativeDate,
  toneOf,
  type UiJobBase,
  type UiSegment,
  type UiSpeaker,
} from "./ui";

/** State kontrak → state UI (uploading/deleted tidak punya kartu sendiri). */
export function uiStatus(job: Job): string {
  if (job.state === "uploading" || job.state === "queued") return "queued";
  if (job.state === "deleted") return "cancelled";
  return job.state;
}

export function extOf(filename: string): string {
  const ext = filename.split(".").pop();
  return (ext ? ext.toUpperCase() : "AUDIO").slice(0, 5);
}

export function titleFromFilename(filename: string): string {
  const base = filename.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ").trim();
  return base === "" ? "Berkas audio" : base.charAt(0).toUpperCase() + base.slice(1);
}

export function uiJobCard(job: Job): UiJobBase {
  const seconds = job.duration_seconds ?? 0;
  return {
    id: job.job_id,
    title: titleFromFilename(job.filename),
    file: job.filename,
    format: extOf(job.filename),
    sizeMb: Math.round((job.size_bytes / 1024 / 1024) * 10) / 10,
    status: uiStatus(job),
    duration: seconds > 0 ? formatClock(seconds) : "—",
    seconds,
    language: languageLabel(job.language),
    diarized: job.diarization,
    date: relativeDate(job.created_at),
  };
}

export function uiSpeakers(speakers: Speaker[]): UiSpeaker[] {
  return speakers.map((s, i) => ({
    name: s.display_name || s.label,
    role: s.label,
    original: s.speaker_id,
    tone: toneOf(i),
  }));
}

export function uiSegments(segments: Segment[], speakers: Speaker[]): UiSegment[] {
  const byId = new Map(speakers.map((s) => [s.speaker_id, s]));
  return segments.map((s) => {
    const sp = s.speaker_id ? byId.get(s.speaker_id) : undefined;
    return {
      speaker: sp ? sp.display_name || sp.label : "Pembicara",
      role: sp ? sp.label : "",
      start: s.start,
      end: s.end,
      time: formatClock(s.start),
      text: s.text,
      confidence: s.confidence,
      edited: Boolean(s.edited),
    };
  });
}

export function uiTranscript(transcript: Transcript): {
  segments: UiSegment[];
  speakers: UiSpeaker[];
} {
  return {
    segments: uiSegments(transcript.segments, transcript.speakers),
    speakers: uiSpeakers(transcript.speakers),
  };
}

export function statusMeta(status: string) {
  return STATUS[status] ?? STATUS.queued;
}

/** Perkiraan progres per tahap (kontrak belum punya persentase). */
export function stageProgress(stage: string | null | undefined): number {
  if (stage === "probing") return 14;
  if (stage === "transcribing") return 52;
  if (stage === "diarizing") return 78;
  if (stage === "merging") return 94;
  return 0;
}
