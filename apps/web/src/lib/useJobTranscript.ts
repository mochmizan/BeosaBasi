// Hook data satu job: detail status, transkrip, audio, sunting segmen,
// ganti nama pembicara, ekspor, dan hapus. Dipakai Home + JobDetail.

import { useCallback, useEffect, useRef, useState } from "react";
import type { JobDetail, Transcript } from "../api-types";
import { api, ApiError } from "../api/client";
import { pesanGalat } from "../api/errors";
import { uiJobCard } from "./adapters";
import { downloadBlob, fileBase } from "./ui";
import { useStudio } from "../components/studio";
import type { ExportFormat } from "../components/Transcript";

const POLL_MS = 4000;

export function useJobTranscript(jobId: string | null) {
  const { toast, refreshData } = useStudio();
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
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
    (index: number, text: string) => {
      if (jobId === null || transcript === null) return;
      const raw = transcript.segments[index];
      if (!raw) return;
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
          toast("Perubahan transkrip disimpan");
        } catch (e) {
          toast(pesanGalat(e));
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
          toast(`Segmen dipindahkan ke ${speakerName}`);
        } catch (e) {
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
          toast(`Label “${oldName}” diubah menjadi “${newName}”`);
        } catch (e) {
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
      void (async () => {
        try {
          const blob = await api.exportTranscript(jobId, format);
          const base = fileBase(uiJobCard(detail.job));
          downloadBlob(`${base}.${format}`, blob);
          toast(`Transkrip ${format.toUpperCase()} diunduh`);
        } catch (e) {
          toast(e instanceof ApiError ? e.message : pesanGalat(e));
        }
      })();
    },
    [detail, jobId, toast],
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
    reload: load,
    editSegment,
    reassign,
    renameSpeaker,
    exportAs,
    deleteJob,
  };
}
