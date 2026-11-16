import { useMemo, useState } from "react";
import {
  ArrowUpRight,
  Clock,
  FileAudio,
  FileUp,
  Globe2,
  Loader2,
  Lock,
  Mic,
  Play,
  Search,
  Sparkles,
  Users,
} from "lucide-react";
import Waveform from "../components/Waveform";
import { useStudio } from "../components/studio";
import { statusMeta, uiJobCard } from "../lib/adapters";

const FILTERS = [
  { id: "all", label: "Semua" },
  { id: "completed", label: "Selesai" },
  { id: "queued", label: "Antrean" },
  { id: "processing", label: "Diproses" },
  { id: "failed", label: "Gagal" },
  { id: "expired", label: "Kedaluwarsa" },
];

export default function JobsPage() {
  const { jobs, query, setQuery, goJob, startNewRecording, startNewUpload, workerOnline } = useStudio();
  const [filter, setFilter] = useState("all");
  const [format, setFormat] = useState("Semua");

  const uiJobs = useMemo(() => jobs.map(uiJobCard), [jobs]);
  const formats = useMemo(() => ["Semua", ...new Set(uiJobs.map((j) => j.format))], [uiJobs]);

  const totals = useMemo(() => {
    const completed = uiJobs.filter((j) => j.status === "completed");
    const seconds = completed.reduce((acc, j) => acc + j.seconds, 0);
    return {
      minutes: Math.round(seconds / 60),
      completed: completed.length,
      total: uiJobs.length,
    };
  }, [uiJobs]);

  const filtered = useMemo(
    () =>
      uiJobs.filter((job) => {
        const haystack = `${job.title} ${job.file} ${job.language} ${job.format}`;
        const matchQuery =
          query.trim() === "" || haystack.toLowerCase().includes(query.trim().toLowerCase());
        const matchFilter = filter === "all" || job.status === filter;
        const matchFormat = format === "Semua" || job.format === format;
        return matchQuery && matchFilter && matchFormat;
      }),
    [uiJobs, query, filter, format],
  );

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Pustaka</div>
          <h1>
            Semua <em>job</em> kamu.
          </h1>
          <p className="page-sub">
            {totals.total} job · {totals.minutes} menit transkrip · audio dihapus ≤24 jam, transkrip
            30 hari.
          </p>
        </div>
        <div className="head-stats">
          <div className="mini-stat">
            <span>Job selesai</span>
            <b>{totals.completed}</b>
          </div>
          <div className="mini-stat">
            <span>Total job</span>
            <b>{totals.total}</b>
          </div>
        </div>
      </div>

      <div className="library-toolbar">
        <div className="filter-chips">
          {FILTERS.map((item) => (
            <button
              key={item.id}
              className={`filter-chip ${filter === item.id ? "is-active" : ""}`}
              onClick={() => setFilter(item.id)}
            >
              {item.id === "processing" ? <Loader2 size={11} /> : null}
              {item.label}
              {item.id !== "all" ? (
                <span className="filter-count">
                  {uiJobs.filter((j) => j.status === item.id).length}
                </span>
              ) : null}
            </button>
          ))}
        </div>
        <div className="toolbar-right">
          <div className="lib-search">
            <Search size={14} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Cari judul, berkas, bahasa…"
              aria-label="Filter pustaka"
            />
          </div>
          <div className="select-wrap lib-format">
            <FileAudio size={14} />
            <select value={format} onChange={(e) => setFormat(e.target.value)} aria-label="Filter format">
              {formats.map((f) => (
                <option key={f} value={f}>
                  {f === "Semua" ? "Semua format" : f}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="rec-grid">
        {filtered.map((job) => {
          const meta = statusMeta(job.status);
          return (
            <article
              key={job.id}
              className={`rec-card status-${job.status}`}
              onClick={() => goJob(job.id)}
            >
              <div className={`rec-thumb tone-${meta.tone}`}>
                <div className="thumb-glow" />
                <Waveform
                  bars={34}
                  seed={job.id.length * 7 + 30}
                  height={58}
                  className="thumb-wave"
                />
                <span className="format-badge">{job.format}</span>
                <span className={`status-pill is-overlay tone-${meta.tone}`}>
                  {job.status === "processing" ? <Loader2 size={10} className="spin" /> : <i />}
                  {job.status === "queued" && !workerOnline ? "Tertunda" : meta.label}
                </span>
                <span className="duration">
                  <Clock size={11} /> {job.duration}
                </span>
                {job.status === "completed" ? (
                  <button
                    className="play-btn"
                    aria-label={`Buka transkrip ${job.title}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      goJob(job.id);
                    }}
                  >
                    <Play size={16} fill="currentColor" />
                  </button>
                ) : null}
              </div>

              <div className="rec-card-body">
                <div className="rec-card-top">
                  <span className={`tag tone-${meta.tone}`}>
                    {job.status === "queued" && !workerOnline ? "Pemrosesan tertunda" : meta.label}
                  </span>
                  <span className="rec-date">{job.date}</span>
                </div>
                <h3>{job.title}</h3>
                <p className="rec-file">
                  <FileAudio size={12} /> {job.file} · {job.sizeMb} MB
                </p>

                {job.status === "queued" ? (
                  <p className="card-note is-amber">
                    {workerOnline
                      ? "Menunggu giliran pekerja transkripsi."
                      : "Perangkat pekerja offline — job aman di antrean."}
                  </p>
                ) : null}

                {job.status === "failed" || job.status === "expired" ? (
                  <p className="card-note is-coral">{meta.note}</p>
                ) : null}

                <div className="rec-card-foot">
                  <span>
                    <Users size={12} /> {job.diarized ? "diarisasi" : "1 pembicara"}
                  </span>
                  <span>
                    <Globe2 size={12} /> {job.language}
                  </span>
                  {job.status === "completed" ? (
                    <span className="rec-acc">
                      <Sparkles size={12} /> selesai
                    </span>
                  ) : (
                    <span className="rec-acc is-muted">
                      <Lock size={12} /> audio ≤24 jam
                    </span>
                  )}
                  <ArrowUpRight size={14} className="rec-open" />
                </div>
              </div>
            </article>
          );
        })}
      </div>

      {filtered.length === 0 ? (
        <div className="empty-library">
          <div className="empty-icon">
            <Search size={22} />
          </div>
          <h3>{uiJobs.length === 0 ? "Belum ada job di pustaka" : "Tidak ada job yang cocok"}</h3>
          <p>
            {uiJobs.length === 0
              ? "Mulai dengan merekam suara dari mikrofon atau mengunggah berkas audio/video."
              : "Coba kata kunci atau filter status lain untuk melihat job yang tersimpan."}
          </p>
          <div className="done-actions">
            {uiJobs.length === 0 ? (
              <>
                <button className="btn btn-primary btn-sm" onClick={startNewRecording}>
                  <Mic size={14} /> Rekam suara
                </button>
                <button className="btn btn-ghost btn-sm" onClick={startNewUpload}>
                  <FileUp size={14} /> Unggah berkas
                </button>
              </>
            ) : (
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  setFilter("all");
                  setFormat("Semua");
                  setQuery("");
                }}
              >
                Reset filter
              </button>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
