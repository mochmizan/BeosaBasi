import { useMemo } from "react";
import {
  ArrowUpRight,
  CalendarDays,
  Clock,
  FileAudio,
  FileUp,
  Lock,
  Mic,
  Sparkles,
  Users,
} from "lucide-react";
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
    prefs,
    inputMode,
    setInputMode,
    startNewRecording,
    startNewUpload,
    workerOnline,
    refreshHealth,
    startUpload,
    resumeUpload,
    cancelUpload,
    goJob,
    navigate,
    toast,
    activeId,
    selectJob,
  } = useStudio();

  const uiJobs = useMemo(() => jobs.map(uiJobCard), [jobs]);

  const featuredId = useMemo(() => {
    if (activeId !== null && jobs.some((j) => j.job_id === activeId)) return activeId;
    const completed = jobs.find((j) => j.state === "completed");
    return completed?.job_id ?? jobs[0]?.job_id ?? null;
  }, [activeId, jobs]);

  const {
    detail,
    transcript,
    audioUrl,
    saveStatus,
    editSegment,
    reassign,
    renameSpeaker,
    exportAs,
    deleteJob,
  } = useJobTranscript(featuredId);

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
            <span className="eyebrow-dot" /> Studio Transkripsi
          </div>
          <h1 className="hero-title">
            Beo digital penyalin suara jadi teks, <em>tanpa basa-basi.</em>
          </h1>
          <p className="page-sub">
            Rekam langsung dari mikrofon atau unggah berkas audio/video. Whisper large-v3-turbo
            mengubahnya jadi transkrip Bahasa Indonesia berpenanda waktu yang siap disunting dan
            diekspor — langsung tanpa akun.
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
          prefs={prefs}
          inputMode={inputMode}
          onChangeMode={setInputMode}
          workerOnline={workerOnline}
          onRefreshWorker={refreshHealth}
          onPickFile={startUpload}
          onResumeUpload={resumeUpload}
          onCancelUpload={cancelUpload}
          onOpenJob={goJob}
          onToast={toast}
        />

        {job ? (
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
                <h3>Belum ada transkrip aktif</h3>
                <p>
                  Rekam suara langsung dari mikrofon atau pilih berkas audio/video di panel sebelah —
                  hasil transkrip berpenanda waktu akan tampil di sini.
                </p>
                <div className="job-state-actions">
                  <button className="btn btn-primary btn-sm" onClick={startNewRecording}>
                    <Mic size={14} /> Rekam suara
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={startNewUpload}>
                    <FileUp size={14} /> Unggah berkas
                  </button>
                </div>
              </div>
            </div>
          </section>
        )}
      </div>

      {recent.length > 0 ? (
        <section className="recent-strip">
          <div className="strip-head">
            <div>
              <h3>Job terakhir</h3>
              <p>Status unggahan, antrean, dan hasil transkrip terbaru di peramban ini.</p>
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
      ) : null}

      <section className="home-banner">
        <div className="banner-glow" />
        <span className="banner-badge">
          <Lock size={12} /> Tanpa Akun
        </span>
        <p>
          Langsung pakai tanpa registrasi. Audio dihapus otomatis dalam <em>24 jam</em>, transkrip
          tersimpan <em>30 hari</em> di sesi peramban ini, dan tidak pernah dipakai melatih model.
        </p>
        <button className="link-btn" onClick={() => navigate("settings")}>
          Kelola sesi <ArrowUpRight size={13} />
        </button>
      </section>
    </div>
  );
}
