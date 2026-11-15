import { useMemo } from "react";
import { ArrowUpRight, CalendarDays, Clock, FileAudio, ShieldCheck, Sparkles, Users } from "lucide-react";
import Uploader from "../components/Uploader";
import Transcript, { type TranscriptJob } from "../components/Transcript";
import Waveform from "../components/Waveform";
import { useStudio } from "../components/studio";
import { statusMeta, uiJobCard, uiTranscript, stageProgress } from "../lib/adapters";
import { useJobTranscript } from "../lib/useJobTranscript";
import { isMac, modKey } from "../lib/platform";
import { PESAN_GALAT } from "../api/errors";

export default function HomePage() {
  const {
    jobs,
    upload,
    quota,
    workerOnline,
    refreshHealth,
    startUpload,
    cancelUpload,
    goJob,
    navigate,
    toast,
    openNotice,
    activeId,
    selectJob,
  } = useStudio();

  const uiJobs = useMemo(() => jobs.map(uiJobCard), [jobs]);

  const featuredId = useMemo(() => {
    if (activeId !== null && jobs.some((j) => j.job_id === activeId)) return activeId;
    const completed = jobs.find((j) => j.state === "completed");
    return completed?.job_id ?? jobs[0]?.job_id ?? null;
  }, [activeId, jobs]);

  const { detail, transcript, audioUrl, editSegment, reassign, renameSpeaker, exportAs, deleteJob } =
    useJobTranscript(featuredId);

  const job: TranscriptJob | null = useMemo(() => {
    if (detail === null) return null;
    const base = uiJobCard(detail.job);
    const parsed = transcript ? uiTranscript(transcript) : { segments: [], speakers: [] };
    return {
      ...base,
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
  }, [audioUrl, detail, transcript]);

  const parsed = transcript ? uiTranscript(transcript) : { segments: [], speakers: [] };
  const recent = uiJobs.filter((item) => item.id !== featuredId).slice(0, 3);

  const today = new Intl.DateTimeFormat("id-ID", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date());

  return (
    <div className="page home-page">
      <div className="page-head home-head">
        <div>
          <div className="eyebrow">
            <span className="eyebrow-dot" /> Studio
          </div>
          <h1 className="hero-title">
            Beo digital penyalin suara jadi teks, <em>tanpa basa-basi.</em>
          </h1>
          <p className="page-sub">
            Kirim audio rapat, kuliah, atau pesan suara. Whisper large-v3-turbo mengubahnya jadi
            transkrip Bahasa Indonesia yang bisa diedit dan diekspor.
          </p>
        </div>
        <div className="head-side">
          <span className="date-chip">
            <CalendarDays size={14} /> {today}
          </span>
          <button
            className="shortcut-chip"
            onClick={() => toast(`Tekan ${modKey}K untuk membuka perintah cepat`)}
          >
            {isMac ? <Sparkles size={12} /> : null}
            {isMac ? "K untuk perintah" : `${modKey}K untuk perintah`}
          </button>
        </div>
      </div>

      <div className="studio-grid">
        <Uploader
          upload={upload}
          quota={quota}
          workerOnline={workerOnline}
          onRefreshWorker={refreshHealth}
          onPickFile={startUpload}
          onCancelUpload={cancelUpload}
          onOpenJob={goJob}
          onOpenConsent={() => openNotice()}
          onToast={toast}
        />

        {job ? (
          <Transcript
            job={job}
            segments={parsed.segments}
            speakers={parsed.speakers}
            audioUrl={audioUrl}
            onEditSegment={editSegment}
            onReassign={reassign}
            onRenameSpeaker={renameSpeaker}
            onExport={exportAs}
            onDeleteJob={deleteJob}
            onNavigate={navigate}
            onToast={toast}
          />
        ) : (
          <section className="panel transcript-panel">
            <div className="transcript-body is-state">
              <div className="job-state">
                <span className="job-state-icon is-slate">
                  <FileAudio size={26} />
                </span>
                <h3>Belum ada transkrip</h3>
                <p>Unggah berkas audio pertamamu — hasilnya muncul di sini.</p>
              </div>
            </div>
          </section>
        )}
      </div>

      <section className="recent-strip">
        <div className="strip-head">
          <div>
            <h3>Job terakhir</h3>
            <p>Status unggahan, antrean, dan hasil transkrip.</p>
          </div>
          <button className="link-btn" onClick={() => navigate("library")}>
            Buka pustaka <ArrowUpRight size={13} />
          </button>
        </div>

        <div className="strip-grid">
          {recent.map((item) => {
            const meta = statusMeta(item.status);
            return (
              <button
                key={item.id}
                className="strip-card"
                onClick={() => selectJob(item.id, item.title)}
              >
                <span className={`strip-icon tone-${meta.tone}`}>
                  <FileAudio size={15} />
                </span>
                <span className="strip-copy">
                  <b>{item.title}</b>
                  <span>
                    <Clock size={11} /> {item.duration}
                    <span className={`status-dot-mini tone-${meta.tone}`} /> {meta.label}
                  </span>
                </span>
                {item.status === "completed" ? (
                  <Waveform
                    bars={14}
                    seed={item.id.length * 7 + 24}
                    height={24}
                    className="strip-wave"
                  />
                ) : null}
                <span className={`status-pill is-compact tone-${meta.tone}`}>
                  {item.diarized ? <Users size={10} /> : null}
                  {item.status === "processing" ? "…" : meta.label}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="home-banner">
        <div className="banner-glow" />
        <span className="banner-badge">
          <ShieldCheck size={12} /> Privasi
        </span>
        <p>
          Audio dihapus otomatis dalam <em>24 jam</em>, transkrip tersimpan <em>30 hari</em>. Audio
          dan transkrip tidak pernah dipakai untuk melatih model.
        </p>
        <button className="link-btn" onClick={() => openNotice()}>
          Baca pemberitahuan <ArrowUpRight size={13} />
        </button>
      </section>
    </div>
  );
}
