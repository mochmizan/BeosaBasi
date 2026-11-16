import { useMemo } from "react";
import { useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import Transcript, { type TranscriptJob } from "../components/Transcript";
import ErrorMessage from "../components/ErrorMessage";
import { useStudio } from "../components/studio";
import { uiJobCard, uiTranscript, stageProgress } from "../lib/adapters";
import { useJobTranscript } from "../lib/useJobTranscript";
import { PESAN_GALAT } from "../api/errors";

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { navigate, toast } = useStudio();
  const jobId = id ?? null;
  const {
    detail,
    transcript,
    audioUrl,
    error,
    loading,
    saveStatus,
    editSegment,
    reassign,
    renameSpeaker,
    exportAs,
    deleteJob,
  } = useJobTranscript(jobId);

  const parsed = transcript ? uiTranscript(transcript) : { segments: [], speakers: [] };

  const job: TranscriptJob | null = useMemo(() => {
    if (detail === null) return null;
    return {
      ...uiJobCard(detail.job),
      queuePosition: detail.queue_position ?? null,
      eta:
        detail.eta_seconds !== null && detail.eta_seconds !== undefined
          ? `±${Math.max(1, Math.round(detail.eta_seconds / 60))} menit`
          : null,
      progress: stageProgress(detail.job.stage),
      stage: detail.job.stage ?? null,
      workerActive: detail.worker_active,
      error: detail.job.error_code ? PESAN_GALAT[detail.job.error_code] : null,
      audioExpires: audioUrl ? "≤24 jam" : undefined,
      words: parsed.segments.reduce(
        (acc, s) => acc + s.text.split(/\s+/).filter(Boolean).length,
        0,
      ),
      speakers: parsed.speakers,
    };
  }, [audioUrl, detail, parsed.segments, parsed.speakers]);

  if (jobId === null) return <ErrorMessage error={new Error("ID pekerjaan hilang.")} />;
  if (error !== null) return <ErrorMessage error={error} />;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <button className="link-btn" onClick={() => navigate("library")}>
            <ArrowLeft size={13} /> Kembali ke pustaka
          </button>
          <h1>
            {job ? job.title : "Memuat pekerjaan…"}
          </h1>
          <p className="page-sub">
            {job
              ? `${job.file} · ${job.duration} · ${job.language}`
              : "Mengambil status dan transkrip dari server."}
          </p>
        </div>
      </div>

      {job === null ? (
        <p className="bb-muted">{loading ? "Memuat status pekerjaan…" : "Pekerjaan tidak ditemukan."}</p>
      ) : (
        <Transcript
          job={job}
          segments={parsed.segments}
          speakers={parsed.speakers}
          audioUrl={audioUrl}
          saveStatus={saveStatus}
          onEditSegment={editSegment}
          onReassign={reassign}
          onRenameSpeaker={renameSpeaker}
          onExport={exportAs}
          onDeleteJob={() => {
            deleteJob();
            navigate("library");
          }}
          onNavigate={navigate}
          onToast={toast}
        />
      )}
    </div>
  );
}
