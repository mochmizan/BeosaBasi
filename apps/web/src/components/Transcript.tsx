import { useEffect, useMemo, useRef, useState, type CSSProperties, type MouseEvent } from "react";
import {
  AlertTriangle,
  Calendar,
  Check,
  Clock,
  Copy,
  Download,
  FileAudio,
  FileText,
  FileType2,
  Globe2,
  Loader2,
  Lock,
  Pause,
  Pencil,
  Play,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Timer,
  UserRound,
  Users,
  X,
  XCircle,
} from "lucide-react";
import {
  STATUS,
  STAGE,
  STAGE_ORDER,
  buildTXT,
  formatClock,
  type UiJobBase,
  type UiSegment,
  type UiSpeaker,
} from "../lib/ui";

export interface TranscriptJob extends UiJobBase {
  queuePosition?: number | null;
  eta?: string | null;
  progress?: number;
  stage?: string | null;
  workerActive?: boolean;
  error?: string | null;
  model?: string;
  audioExpires?: string;
  words?: number;
}

const EXPORTS = [
  { id: "txt", label: "TXT", desc: "Teks polos dengan timestamp dan nama pembicara." },
  { id: "srt", label: "SRT", desc: "Subtitle untuk editor video dan pemutar media." },
  { id: "vtt", label: "VTT", desc: "WebVTT untuk pemutar web dan platform e-learning." },
  { id: "docx", label: "DOCX", desc: "Dokumen Word siap diedit dan dibagikan." },
] as const;

type ExportFormat = (typeof EXPORTS)[number]["id"];
export type { ExportFormat };

function speakerTone(speakers: UiSpeaker[], name: string) {
  return speakers.find((s) => s.name === name)?.tone ?? "coral";
}

function StatusBody({
  job,
  onNavigate,
  onDeleteJob,
  onToast,
}: {
  job: TranscriptJob;
  onNavigate: (view: "home" | "library" | "insights" | "settings") => void;
  onDeleteJob: (id: string) => void;
  onToast: (message: string) => void;
}) {
  const meta = STATUS[job.status] ?? STATUS.queued;

  if (job.status === "queued") {
    return (
      <div className="job-state">
        <span className="job-state-icon is-amber">
          <Timer size={26} />
        </span>
        <h3>Menunggu antrean</h3>
        <p>{meta.note} Posisi dan perkiraan waktu bisa berubah sesuai beban pekerja.</p>
        <div className="job-state-stats">
          <div>
            <span>Posisi</span>
            <b>#{job.queuePosition ?? 1}</b>
          </div>
          <div>
            <span>Perkiraan mulai</span>
            <b>{job.eta ?? "±3 menit"}</b>
          </div>
          <div>
            <span>Durasi audio</span>
            <b>{job.duration}</b>
          </div>
        </div>
        <div className="job-state-actions">
          <button className="btn btn-ghost btn-sm" onClick={() => onDeleteJob(job.id)}>
            <X size={14} /> Hapus job
          </button>
        </div>
        <p className="job-state-note">
          <Lock size={12} /> Audio menunggu di penyimpanan sementara, maksimal 24 jam.
        </p>
      </div>
    );
  }

  if (job.status === "processing") {
    const index = job.stage ? STAGE_ORDER.indexOf(job.stage as (typeof STAGE_ORDER)[number]) : -1;
    return (
      <div className="job-state is-wide">
        <span className="job-state-icon is-violet">
          <Loader2 size={26} className="spin" />
        </span>
        <h3>{job.stage ? STAGE[job.stage]?.label ?? "Memproses audio" : "Memproses audio"}</h3>
        <p>Whisper large-v3-turbo sedang bekerja. Kamu boleh menutup tab ini.</p>
        <div className="job-progress">
          <div className="job-progress-bar">
            <i style={{ width: `${job.progress ?? 0}%` }} />
          </div>
          <span>{Math.round(job.progress ?? 0)}%</span>
        </div>
        <ol className="stage-list is-stacked">
          {STAGE_ORDER.map((key, i) => {
            const skipped = key === "diarizing" && !job.diarized;
            const done = !skipped && (i < index || (job.progress ?? 0) >= 100);
            const current = !skipped && i === index;
            return (
              <li
                key={key}
                className={`stage-item ${done ? "is-done" : ""} ${current ? "is-current" : ""} ${
                  skipped ? "is-skipped" : ""
                }`}
              >
                <span className="stage-dot">
                  {done ? <Check size={11} /> : current ? <Loader2 size={11} className="spin" /> : null}
                </span>
                <span>{STAGE[key].label}</span>
                {skipped ? <em>dilewati</em> : null}
              </li>
            );
          })}
        </ol>
        <div className="job-state-actions">
          <button className="btn btn-ghost btn-sm" onClick={() => onDeleteJob(job.id)}>
            <X size={14} /> Hapus job
          </button>
        </div>
      </div>
    );
  }

  if (job.status === "failed") {
    return (
      <div className="job-state">
        <span className="job-state-icon is-coral">
          <AlertTriangle size={26} />
        </span>
        <h3>Job gagal diproses</h3>
        <p>{job.error ?? "Terjadi kesalahan saat memproses audio."}</p>
        <div className="job-state-actions">
          <button className="btn btn-primary btn-sm" onClick={() => onNavigate("home")}>
            <RotateCcw size={14} /> Unggah ulang
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => onDeleteJob(job.id)}>
            Hapus dari pustaka
          </button>
        </div>
        <p className="job-state-note">
          <ShieldCheck size={12} /> Tidak ada transkrip yang dibuat. Audio gagal sudah dihapus.
        </p>
      </div>
    );
  }

  if (job.status === "expired") {
    return (
      <div className="job-state">
        <span className="job-state-icon is-slate">
          <Clock size={26} />
        </span>
        <h3>Job kedaluwarsa</h3>
        <p>{job.error ?? "Job menunggu terlalu lama sehingga audio dihapus otomatis."}</p>
        <div className="job-state-actions">
          <button className="btn btn-primary btn-sm" onClick={() => onNavigate("home")}>
            <RotateCcw size={14} /> Unggah ulang
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => onDeleteJob(job.id)}>
            Hapus dari pustaka
          </button>
        </div>
        <p className="job-state-note">
          <ShieldCheck size={12} /> Retensi audio berakhir sebelum job sempat diproses.
        </p>
      </div>
    );
  }

  if (job.status === "cancelled") {
    return (
      <div className="job-state">
        <span className="job-state-icon is-slate">
          <XCircle size={26} />
        </span>
        <h3>Job dibatalkan</h3>
        <p>Job ini dibatalkan sebelum selesai. Tidak ada transkrip yang disimpan.</p>
        <div className="job-state-actions">
          <button className="btn btn-ghost btn-sm" onClick={() => onDeleteJob(job.id)}>
            Hapus dari pustaka
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => onNavigate("home")}>
            Unggah berkas baru
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="job-state">
      <span className="job-state-icon is-slate">
        <FileText size={26} />
      </span>
      <h3>Transkrip belum tersedia</h3>
      <p>Job ini belum punya segmen transkrip yang bisa ditampilkan.</p>
      <div className="job-state-actions">
        <button className="btn btn-ghost btn-sm" onClick={() => onToast("Coba muat ulang halaman")}>
          Muat ulang
        </button>
      </div>
    </div>
  );
}

function SpeakerRow({
  speaker,
  stats,
  onRename,
}: {
  speaker: UiSpeaker;
  stats: { segments: number; words: number };
  onRename: (oldName: string, newName: string) => void;
}) {
  const [name, setName] = useState(speaker.name);

  useEffect(() => {
    setName(speaker.name);
  }, [speaker.name]);

  const commit = () => {
    const next = name.trim();
    if (next !== "" && next !== speaker.name) onRename(speaker.name, next);
    else setName(speaker.name);
  };

  return (
    <li className="speaker-row">
      <span className={`avatar avatar-md tone-${speaker.tone}`}>{speaker.name.charAt(0)}</span>
      <div className="speaker-main">
        <input
          className="speaker-name-input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
            if (e.key === "Escape") {
              setName(speaker.name);
              e.currentTarget.blur();
            }
          }}
          aria-label={`Ubah nama ${speaker.name}`}
        />
        <span className="speaker-sub">
          {speaker.original ? `${speaker.original} · ` : ""}
          {speaker.role}
        </span>
      </div>
      <div className="speaker-stats">
        <div>
          <b>{stats.segments}</b>
          <span>segmen</span>
        </div>
        <div>
          <b>{stats.words}</b>
          <span>kata</span>
        </div>
      </div>
    </li>
  );
}

export default function Transcript({
  job,
  segments,
  speakers,
  audioUrl,
  onEditSegment,
  onReassign,
  onRenameSpeaker,
  onExport,
  onDeleteJob,
  onNavigate,
  onToast,
}: {
  job: TranscriptJob;
  segments: UiSegment[];
  speakers: UiSpeaker[];
  audioUrl: string | null;
  onEditSegment: (index: number, text: string) => void;
  onReassign: (index: number, speaker: string) => void;
  onRenameSpeaker: (oldName: string, newName: string) => void;
  onExport: (format: ExportFormat) => void;
  onDeleteJob: (id: string) => void;
  onNavigate: (view: "home" | "library" | "insights" | "settings") => void;
  onToast: (message: string) => void;
}) {
  const [tab, setTab] = useState<"transcript" | "speakers" | "export">("transcript");
  const [current, setCurrent] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const skipSave = useRef(false);
  const audioRef = useRef<HTMLAudioElement>(null);

  const seconds = job.seconds || 0;
  const canRead = job.status === "completed" && segments.length > 0;
  const audioAvailable = Boolean(audioUrl);
  const status = STATUS[job.status] ?? STATUS.queued;

  useEffect(() => {
    setTab("transcript");
    setCurrent(0);
    setPlaying(false);
    setEditingId(null);
  }, [job.id]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onTime = () => setCurrent(audio.currentTime);
    const onEnd = () => setPlaying(false);
    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("ended", onEnd);
    return () => {
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("ended", onEnd);
    };
  }, [audioUrl]);

  const activeIndex = useMemo(
    () =>
      segments.reduce(
        (acc, s, i) => ((s.start || 0) <= current ? i : acc),
        segments.length > 0 ? 0 : -1,
      ),
    [segments, current],
  );

  const seek = (value: number, autoPlay = true) => {
    if (!audioAvailable) {
      onToast("Audio sudah dihapus otomatis. Transkrip tetap tersimpan 30 hari.");
      return;
    }
    const audio = audioRef.current;
    const target = Math.max(0, Math.min(seconds, value));
    setCurrent(target);
    if (audio) {
      audio.currentTime = target;
      if (autoPlay) {
        void audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
      } else {
        setPlaying(!audio.paused);
      }
    }
  };

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      void audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
    } else {
      audio.pause();
      setPlaying(false);
    }
  };

  const seekFromEvent = (e: MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    seek(Math.round(ratio * seconds), false);
  };

  const startEdit = (index: number) => {
    skipSave.current = false;
    setEditingId(index);
    setDraft(segments[index].text);
  };

  const saveEdit = (index: number) => {
    if (skipSave.current) {
      skipSave.current = false;
      setEditingId(null);
      return;
    }
    const nextText = draft.trim();
    if (nextText !== "" && nextText !== segments[index].text) {
      onEditSegment(index, nextText);
    }
    setEditingId(null);
  };

  const copyAll = async () => {
    if (!canRead) return;
    try {
      await navigator.clipboard.writeText(buildTXT(job, segments));
      onToast("Transkrip disalin ke clipboard");
    } catch {
      onToast("Clipboard tidak tersedia di browser ini");
    }
  };

  const speakerStats = useMemo(() => {
    const map = new Map<string, { segments: number; words: number }>();
    speakers.forEach((s) => map.set(s.name, { segments: 0, words: 0 }));
    segments.forEach((s) => {
      const entry = map.get(s.speaker) ?? { segments: 0, words: 0 };
      entry.segments += 1;
      entry.words += s.text.trim().split(/\s+/).filter(Boolean).length;
      map.set(s.speaker, entry);
    });
    return map;
  }, [speakers, segments]);

  const pct = seconds > 0 ? (current / seconds) * 100 : 0;
  const lowConfidence = segments.filter((s) => (s.confidence ?? 1) < 0.85).length;

  return (
    <section className="panel transcript-panel">
      {audioUrl ? <audio ref={audioRef} src={audioUrl} preload="metadata" /> : null}

      <div className="transcript-head">
        <div className="tabs" role="tablist" aria-label="Panel transkrip">
          <button
            className={`tab ${tab === "transcript" ? "is-active" : ""}`}
            onClick={() => setTab("transcript")}
            role="tab"
            aria-selected={tab === "transcript"}
          >
            <FileText size={15} /> Transkrip
            {lowConfidence > 0 ? <span className="tab-count">{lowConfidence}</span> : null}
          </button>
          <button
            className={`tab ${tab === "speakers" ? "is-active" : ""}`}
            onClick={() => setTab("speakers")}
            role="tab"
            aria-selected={tab === "speakers"}
          >
            <Users size={15} /> Pembicara
            <span className="tab-count">{speakers.length}</span>
          </button>
          <button
            className={`tab ${tab === "export" ? "is-active" : ""}`}
            onClick={() => setTab("export")}
            role="tab"
            aria-selected={tab === "export"}
          >
            <Download size={15} /> Ekspor
          </button>
        </div>

        <div className="t-actions">
          <button className="icon-btn" onClick={copyAll} title="Salin transkrip" disabled={!canRead}>
            <Copy size={16} />
          </button>
          <button
            className="icon-btn"
            onClick={() => onExport("txt")}
            title="Unduh TXT"
            disabled={!canRead}
          >
            <Download size={16} />
          </button>
        </div>
      </div>

      <div className="transcript-meta">
        <div className="meta-title-row">
          <h2>{job.title}</h2>
          <span className={`status-pill tone-${status.tone}`}>
            {job.status === "processing" ? <Loader2 size={11} className="spin" /> : <i />}
            {status.label}
          </span>
        </div>
        <div className="meta-row">
          <span>
            <Calendar size={13} /> {job.date}
          </span>
          <span>
            <Clock size={13} /> {job.duration}
          </span>
          <span title={job.file}>
            <FileAudio size={13} /> {job.format} · {job.sizeMb} MB
          </span>
          <span>
            <Globe2 size={13} /> {job.language}
          </span>
        </div>
        <div className="meta-bottom">
          <div className="speaker-stack">
            {speakers.slice(0, 4).map((s) => (
              <span key={s.name} className={`avatar avatar-xs tone-${s.tone}`} title={`${s.name} — ${s.role}`}>
                {s.name.charAt(0)}
              </span>
            ))}
            {speakers.length > 4 ? (
              <span className="avatar avatar-xs more">+{speakers.length - 4}</span>
            ) : null}
          </div>
          <span className="meta-names">
            {job.diarized
              ? speakers.map((s) => s.name).join(" · ")
              : "Pelabelan pembicara tidak aktif"}
          </span>
          <span className="retention-badge" title="Batas penyimpanan audio">
            <ShieldCheck size={12} /> {audioAvailable ? `Audio ${job.audioExpires ?? "24 jam"}` : "Audio terhapus"}
          </span>
        </div>
      </div>

      {canRead ? (
        <div className={`player-bar ${audioAvailable ? "" : "is-disabled"}`}>
          <button
            className="player-btn"
            onClick={togglePlay}
            aria-label={playing ? "Jeda audio" : "Putar audio"}
            disabled={!audioAvailable}
          >
            {playing ? <Pause size={15} fill="currentColor" /> : <Play size={15} fill="currentColor" />}
          </button>
          <span className="player-time">{formatClock(current)}</span>
          <div
            className="player-track"
            onClick={seekFromEvent}
            role="slider"
            aria-label="Posisi audio"
            aria-valuemin={0}
            aria-valuemax={seconds}
            aria-valuenow={Math.round(current)}
            tabIndex={audioAvailable ? 0 : -1}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight") seek(current + 5, false);
              if (e.key === "ArrowLeft") seek(current - 5, false);
            }}
          >
            <i style={{ width: `${pct}%` }} />
            <span className="player-knob" style={{ left: `${pct}%` }} />
          </div>
          <span className="player-time">{formatClock(seconds)}</span>
          <span className="player-note">
            {audioAvailable ? (
              <>
                <ShieldCheck size={12} /> sisa {job.audioExpires ?? "24 jam"}
              </>
            ) : (
              <>
                <Lock size={12} /> audio dihapus otomatis
              </>
            )}
          </span>
        </div>
      ) : null}

      <div className={`transcript-body ${canRead ? "" : "is-state"}`}>
        {!canRead ? (
          <StatusBody job={job} onNavigate={onNavigate} onDeleteJob={onDeleteJob} onToast={onToast} />
        ) : null}

        {canRead && tab === "transcript" ? (
          <div className="segments">
            {segments.map((s, i) => {
              const currentSeg = i === activeIndex && (playing || current > 0);
              const editing = editingId === i;
              return (
                <article
                  key={`${s.start}-${i}`}
                  className={`segment ${currentSeg ? "is-current" : ""} ${editing ? "is-editing" : ""}`}
                  style={{ "--delay": `${Math.min(i, 6) * 40}ms` } as CSSProperties}
                  onClick={(e) => {
                    if ((e.target as HTMLElement).closest("button, select, textarea, input, a, label")) return;
                    seek(s.start || 0);
                  }}
                  title="Klik segmen untuk memutar dari sini"
                >
                  <button
                    className={`avatar avatar-sm tone-${speakerTone(speakers, s.speaker)}`}
                    onClick={() => seek(s.start || 0)}
                    aria-label={`Putar dari ${s.time}`}
                  >
                    {s.speaker.charAt(0)}
                  </button>
                  <div className="segment-main">
                    <div className="segment-head">
                      <b>{s.speaker}</b>
                      <span className="segment-role">{s.role}</span>
                      <button className="segment-time" onClick={() => seek(s.start || 0)}>
                        {s.time}
                      </button>
                      {s.edited ? <span className="edit-badge">diedit</span> : null}
                      {(s.confidence ?? 1) < 0.85 ? (
                        <span
                          className="low-conf"
                          title={`Model kurang yakin (${Math.round((s.confidence ?? 0) * 100)}%). Periksa bagian ini.`}
                        >
                          <AlertTriangle size={10} /> keyakinan rendah
                        </span>
                      ) : null}
                      <div className="segment-tools">
                        <select
                          className="segment-speaker"
                          value={s.speaker}
                          onChange={(e) => onReassign(i, e.target.value)}
                          aria-label={`Pindahkan segmen ${i + 1} ke pembicara lain`}
                          title="Pindahkan segmen ke pembicara lain"
                        >
                          {speakers.map((sp) => (
                            <option key={sp.name} value={sp.name}>
                              {sp.name}
                            </option>
                          ))}
                        </select>
                        <button
                          className="seg-edit"
                          onClick={() => startEdit(i)}
                          aria-label={`Edit segmen ${i + 1}`}
                          title="Edit teks"
                        >
                          <Pencil size={12} />
                        </button>
                      </div>
                    </div>

                    {editing ? (
                      <div className="segment-edit">
                        <textarea
                          autoFocus
                          value={draft}
                          onChange={(e) => setDraft(e.target.value)}
                          onBlur={() => saveEdit(i)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                              e.preventDefault();
                              e.currentTarget.blur();
                            }
                            if (e.key === "Escape") {
                              e.preventDefault();
                              skipSave.current = true;
                              e.currentTarget.blur();
                            }
                          }}
                          rows={3}
                        />
                        <div className="segment-edit-foot">
                          <span>Enter simpan · Esc batal</span>
                          <button className="btn btn-primary btn-xs" onClick={() => saveEdit(i)}>
                            <Check size={12} /> Simpan
                          </button>
                        </div>
                      </div>
                    ) : (
                      <p>{s.text}</p>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        ) : null}

        {canRead && tab === "speakers" ? (
          <div className="speakers-tab">
            <div className="panel-inline-head">
              <div>
                <h3>Label pembicara</h3>
                <p>Berlaku untuk transkrip ini saja, tidak untuk rekaman lain.</p>
              </div>
              <span className="pill-soft">
                <Users size={11} /> maks 8
              </span>
            </div>

            {!job.diarized ? (
              <div className="inline-notice">
                <UserRound size={16} />
                <p>
                  Pelabelan pembicara tidak diaktifkan untuk job ini. Aktifkan saat mengunggah
                  berikutnya — biayanya 2× kuota.
                </p>
                <button className="btn btn-ghost btn-sm" onClick={() => onNavigate("home")}>
                  Unggah dengan label
                </button>
              </div>
            ) : null}

            <ul className="speaker-list">
              {speakers.map((speaker) => (
                <SpeakerRow
                  key={speaker.name}
                  speaker={speaker}
                  stats={speakerStats.get(speaker.name) ?? { segments: 0, words: 0 }}
                  onRename={onRenameSpeaker}
                />
              ))}
            </ul>

            <div className="speakers-help">
              <Sparkles size={13} />
              <span>
                Untuk memindahkan satu segmen, buka tab Transkrip lalu ubah dropdown di kanan nama
                pembicara.
              </span>
            </div>
          </div>
        ) : null}

        {canRead && tab === "export" ? (
          <div className="export-tab">
            <div className="panel-inline-head">
              <div>
                <h3>Ekspor transkrip</h3>
                <p>Ekspor tetap bisa dilakukan meskipun audio sudah dihapus.</p>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={copyAll}>
                <Copy size={13} /> Salin semua
              </button>
            </div>

            <div className="export-grid">
              {EXPORTS.map((item) => (
                <div key={item.id} className={`export-card is-${item.id}`}>
                  <span className="export-icon">
                    {item.id === "docx" ? <FileType2 size={18} /> : <FileText size={18} />}
                  </span>
                  <div className="export-copy">
                    <b>{item.label}</b>
                    <p>{item.desc}</p>
                  </div>
                  <button className="btn btn-ghost btn-sm" onClick={() => onExport(item.id)}>
                    <Download size={13} /> Unduh
                  </button>
                </div>
              ))}
            </div>

            <div className="export-note">
              <ShieldCheck size={13} />
              <span>
                Transkrip tersimpan 30 hari. Setelah itu, ekspor apa pun tidak lagi tersedia kecuali
                kamu menyimpannya sendiri.
              </span>
            </div>
          </div>
        ) : null}
      </div>

      <div className="transcript-foot">
        <span>
          <span className={`foot-dot ${canRead ? "" : "is-idle"}`} />
          {canRead ? "Perubahan tersimpan otomatis" : status.note}
        </span>
        <span className="foot-model">
          <Globe2 size={12} /> {job.model ?? "whisper-large-v3-turbo"}
          {canRead ? ` · ${(job.words ?? 0).toLocaleString("id-ID")} kata` : ""}
        </span>
      </div>
    </section>
  );
}
