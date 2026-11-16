// Hook data satu job: detail status, transkrip, audio, sunting segmen,
// ganti nama pembicara, ekspor, dan hapus. Dipakai Home + JobDetail.

import { useCallback, useEffect, useRef, useState } from "react";
import type { JobDetail, Transcript } from "../api-types";
import { api, ApiError } from "../api/client";
import { pesanGalat } from "../api/errors";
import { uiJobCard, uiTranscript } from "./adapters";
import { buildSRT, buildTXT, buildVTT, downloadBlob, downloadText, fileBase } from "./ui";
import { useStudio } from "../components/studio";
import type { ExportFormat } from "../components/Transcript";

const POLL_MS = 4000;

export type SaveStatus = "idle" | "saving" | "saved" | "conflict" | "error";

export function useJobTranscript(jobId: string | null) {
  const { toast, refreshData, prefs } = useStudio();
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const activeId = useRef<string | null>(null);

  const load = useCallback(async () => {
    if (jobId === null) {
      setDetail(null);
      setTranscript(null);
      setAudioUrl(null);
      return;
    }
    setLoading(true);
    try {
      const d = await api.getJob(jobId);
      if (activeId.current !== jobId) return;
      setDetail(d);
      setError(null);
      if (d.job.state === "completed") {
        const t = await api.getTranscript(jobId);
        if (activeId.current !== jobId) return;
        setTranscript(t);
        try {
          const audio = await api.getAudioUrl(jobId);
          if (activeId.current === jobId) setAudioUrl(audio.url);
        } catch {
          if (activeId.current === jobId) setAudioUrl(null);
        }
      } else {
        setTranscript(null);
        setAudioUrl(null);
      }
    } catch (e) {
      if (activeId.current === jobId) setError(e);
    } finally {
      if (activeId.current === jobId) setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    activeId.current = jobId;
    setDetail(null);
    setTranscript(null);
    setAudioUrl(null);
    setError(null);
    setSaveStatus("idle");
    void load();
  }, [jobId, load]);

  useEffect(() => {
    if (detail === null) return;
    if (!["queued", "processing", "uploading"].includes(detail.job.state)) return;
    const id = setInterval(() => {
      void load();
    }, POLL_MS);
    return () => clearInterval(id);
  }, [detail, load]);

  const editSegment = useCallback(
    (index: number, text: string, silent = false) => {
      if (jobId === null || transcript === null) return;
      const raw = transcript.segments[index];
      if (!raw || raw.text === text) return;
      setSaveStatus("saving");
      setTranscript((prev) =>
        prev === null
          ? prev
          : {
              ...prev,
              segments: prev.segments.map((s, i) =>
                i === index ? { ...s, text, edited: true } : s,
              ),
            },
      );
      void (async () => {
        try {
          const updated = await api.patchSegment(jobId, raw.index, {
            text,
            version: raw.version,
          });
          setTranscript((prev) =>
            prev === null
              ? prev
              : {
                  ...prev,
                  segments: prev.segments.map((s, i) => (i === index ? updated : s)),
                },
          );
          setSaveStatus("saved");
          if (!silent) toast("Perubahan transkrip disimpan");
        } catch (e) {
          if (e instanceof ApiError && e.status === 409) {
            setSaveStatus("conflict");
            toast("Segmen telah diubah di tab lain. Memuat versi terbaru…");
          } else {
            setSaveStatus("error");
            toast(pesanGalat(e));
          }
          void load();
        }
      })();
    },
    [jobId, load, toast, transcript],
  );

  const reassign = useCallback(
    (index: number, speakerName: string) => {
      if (jobId === null || transcript === null) return;
      const raw = transcript.segments[index];
      const speaker = transcript.speakers.find(
        (s) => (s.display_name || s.label) === speakerName,
      );
      if (!raw || !speaker) return;
      setSaveStatus("saving");
      setTranscript((prev) =>
        prev === null
          ? prev
          : {
              ...prev,
              segments: prev.segments.map((s, i) =>
                i === index ? { ...s, speaker_id: speaker.speaker_id } : s,
              ),
            },
      );
      void (async () => {
        try {
          const updated = await api.patchSegment(jobId, raw.index, {
            speaker_id: speaker.speaker_id,
            version: raw.version,
          });
          setTranscript((prev) =>
            prev === null
              ? prev
              : {
                  ...prev,
                  segments: prev.segments.map((s, i) => (i === index ? updated : s)),
                },
          );
          setSaveStatus("saved");
          toast(`Segmen dipindahkan ke ${speakerName}`);
        } catch (e) {
          setSaveStatus("error");
          toast(pesanGalat(e));
          void load();
        }
      })();
    },
    [jobId, load, toast, transcript],
  );

  const renameSpeaker = useCallback(
    (oldName: string, newName: string) => {
      if (jobId === null || transcript === null) return;
      const speaker = transcript.speakers.find(
        (s) => (s.display_name || s.label) === oldName,
      );
      if (!speaker) return;
      setSaveStatus("saving");
      setTranscript((prev) =>
        prev === null
          ? prev
          : {
              ...prev,
              speakers: prev.speakers.map((s) =>
                s.speaker_id === speaker.speaker_id ? { ...s, display_name: newName } : s,
              ),
            },
      );
      void (async () => {
        try {
          const updated = await api.renameSpeaker(jobId, speaker.speaker_id, {
            display_name: newName,
          });
          setTranscript((prev) =>
            prev === null
              ? prev
              : {
                  ...prev,
                  speakers: prev.speakers.map((s) =>
                    s.speaker_id === updated.speaker_id ? updated : s,
                  ),
                },
          );
          setSaveStatus("saved");
          toast(`Label “${oldName}” diubah menjadi “${newName}”`);
        } catch (e) {
          setSaveStatus("error");
          toast(pesanGalat(e));
          void load();
        }
      })();
    },
    [jobId, load, toast, transcript],
  );

  const exportAs = useCallback(
    (format: ExportFormat) => {
      if (jobId === null || detail === null) return;
      const base = fileBase(uiJobCard(detail.job));

      // Bila pengguna menonaktifkan label pembicara di pengaturan untuk TXT/SRT/VTT,
      // kita dapat mengekspor langsung dari segmen terbaru atau melalui endpoint server.
      if (!prefs.includeSpeakerLabels && transcript !== null && format !== "docx") {
        const parsed = uiTranscript(transcript);
        const stripped = parsed.segments.map((s) => ({ ...s, speaker: "", role: "" }));
        if (format === "txt") {
          downloadText(`${base}.txt`, buildTXT(uiJobCard(detail.job), stripped, false));
        } else if (format === "srt") {
          downloadText(`${base}.srt`, buildSRT(stripped, false));
        } else {
          downloadText(`${base}.vtt`, buildVTT(stripped, false));
        }
        toast(`Transkrip ${format.toUpperCase()} (tanpa label pembicara) diunduh`);
        return;
      }

      void (async () => {
        try {
          const blob = await api.exportTranscript(jobId, format);
          downloadBlob(`${base}.${format}`, blob);
          toast(`Transkrip ${format.toUpperCase()} diunduh`);
        } catch (e) {
          // Fallback ke penyusun lokal untuk TXT/SRT/VTT bila server mock tidak mengirim binary
          if (transcript !== null && format !== "docx") {
            const parsed = uiTranscript(transcript);
            if (format === "txt") {
              downloadText(`${base}.txt`, buildTXT(uiJobCard(detail.job), parsed.segments));
            } else if (format === "srt") {
              downloadText(`${base}.srt`, buildSRT(parsed.segments));
            } else {
              downloadText(`${base}.vtt`, buildVTT(parsed.segments));
            }
            toast(`Transkrip ${format.toUpperCase()} diunduh`);
            return;
          }
          toast(e instanceof ApiError ? e.message : pesanGalat(e));
        }
      })();
    },
    [detail, jobId, prefs.includeSpeakerLabels, toast, transcript],
  );

  const deleteJob = useCallback(() => {
    if (jobId === null) return;
    void (async () => {
      try {
        await api.deleteJob(jobId);
        refreshData();
        toast("Job dihapus dari pustaka");
      } catch (e) {
        toast(pesanGalat(e));
      }
    })();
  }, [jobId, refreshData, toast]);

  return {
    detail,
    transcript,
    audioUrl,
    error,
    loading,
    saveStatus,
    reload: load,
    editSegment,
    reassign,
    renameSpeaker,
    exportAs,
    deleteJob,
  };
}
