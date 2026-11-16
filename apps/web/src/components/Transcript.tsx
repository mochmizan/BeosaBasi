import { useEffect, useMemo, useRef, useState, type CSSProperties, type MouseEvent } from "react";
import {
  AlertTriangle,
  Calendar,
  Check,
  Clock,
  Copy,
  Download,
  FastForward,
  FileAudio,
  FileText,
  FileType2,
  Filter,
  Globe2,
  Loader2,
  Lock,
  Pause,
  Pencil,
  Play,
  Rewind,
  RotateCcw,
  Search,
  Sparkles,
  Timer,
  Trash2,
  UserRound,
  Users,
  WifiOff,
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
import type { SaveStatus } from "../lib/useJobTranscript";

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
  { id: "srt", label: "SRT", desc: "Subtitle SubRip untuk editor video dan pemutar media." },
  { id: "vtt", label: "VTT", desc: "WebVTT untuk pemutar web dan platform e-learning." },
  { id: "docx", label: "DOCX", desc: "Dokumen Word siap diedit dan dibagikan." },
] as const;

const SPEEDS = [0.75, 1, 1.25, 1.5, 2] as const;
const AUTOSAVE_MS = 2000;

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
  const workerOffline = job.workerActive === false;

  if (job.status === "queued") {
    return (
      <div className="job-state is-wide">
        <span className="job-state-icon is-amber">
          <Timer size={26} />
        </span>
        <h3>{workerOffline ? "Pemrosesan tertunda (pekerja offline)" : "Menunggu antrean"}</h3>
        <p>
          {workerOffline
            ? "Perangkat pekerja GPU sedang mati. Job kamu aman di antrean dan akan jalan otomatis begitu perangkat aktif."
            : `${meta.note} Posisi dan perkiraan waktu diperbarui otomatis tiap beberapa detik.`}
        </p>
        <div className="job-state-stats">
          <div>
            <span>Posisi</span>
            <b>#{job.queuePosition ?? 1}</b>
          </div>
          <div>
            <span>Perkiraan mulai</span>
            <b>{workerOffline ? "Menunggu pekerja" : job.eta ?? "±2 menit"}</b>
          </div>
          <div>
            <span>Durasi audio</span>
            <b>{job.duration}</b>
          </div>
        </div>
        {workerOffline ? (
          <div className="offline-note">
            <WifiOff size={16} />
            <p>
              <b>Tidak ada status “diproses” palsu.</b> Job menunggu sampai pekerja berdetak kembali
              (maksimal 72 jam).
            </p>
          </div>
        ) : null}
        <div className="job-state-actions">
          <button className="btn btn-ghost btn-sm" onClick={() => onDeleteJob(job.id)}>
            <X size={14} /> Batalkan & hapus job
          </button>
        </div>
        <p className="job-state-note">
          <Lock size={12} /> Audio menunggu di penyimpanan sementara, maksimal 24 jam setelah selesai.
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
            <RotateCcw size={14} /> Coba lagi
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => onDeleteJob(job.id)}>
            Hapus dari pustaka
          </button>
        </div>
        <p className="job-state-note">
          <Lock size={12} /> Tidak ada transkrip yang disimpan. Audio gagal dihapus otomatis.
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
            Transkripsi baru
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
        <button className="btn btn-ghost btn-sm" onClick={() => onToast("Menyegarkan data…")}>
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
  saveStatus = "idle",
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
  saveStatus?: SaveStatus;
  onEditSegment: (index: number, text: string, silent?: boolean) => void;
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
  const [speed, setSpeed] = useState<number>(1);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [segSearch, setSegSearch] = useState("");
  const [onlyLowConf, setOnlyLowConf] = useState(false);
  const [speakerFilter, setSpeakerFilter] = useState("ALL");
  const [confirmDelete, setConfirmDelete] = useState(false);

  const skipSave = useRef(false);
  const lastAutosaved = useRef<string>("");
  const autosaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
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
    setSegSearch("");
    setOnlyLowConf(false);
    setSpeakerFilter("ALL");
    setConfirmDelete(false);
  }, [job.id]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.playbackRate = speed;
  }, [speed, audioUrl]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onTime = () => setCurrent(audio.currentTime);
    const onEnd = () => setPlaying(false);
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("ended", onEnd);
    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    return () => {
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("ended", onEnd);
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
    };
  }, [audioUrl]);

  // Debounced autosave ≤ 2 detik saat menyunting segmen (TK-044: wajib ≤ 5 detik)
  useEffect(() => {
    if (editingId === null) return;
    const original = segments[editingId]?.text ?? "";
    const trimmed = draft.trim();
    if (trimmed === "" || trimmed === original || trimmed === lastAutosaved.current) {
      return;
    }
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    autosaveTimer.current = setTimeout(() => {
      lastAutosaved.current = trimmed;
      onEditSegment(editingId, trimmed, true);
    }, AUTOSAVE_MS);
    return () => {
      if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    };
  }, [draft, editingId, onEditSegment, segments]);

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
      onToast("Audio sudah dihapus sesuai retensi 24 jam. Transkrip tetap bisa disunting.");
      return;
    }
    const audio = audioRef.current;
    const cap = seconds > 0 ? seconds : audio?.duration || 999999;
    const target = Math.max(0, Math.min(cap, value));
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

  const cycleSpeed = () => {
    const idx = SPEEDS.indexOf(speed as (typeof SPEEDS)[number]);
    const next = SPEEDS[(idx + 1) % SPEEDS.length];
    setSpeed(next);
  };

  const seekFromEvent = (e: MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    seek(Math.round(ratio * seconds * 10) / 10, false);
  };

  const startEdit = (index: number) => {
    skipSave.current = false;
    lastAutosaved.current = segments[index].text;
    setEditingId(index);
    setDraft(segments[index].text);
  };

  const saveEdit = (index: number) => {
    if (autosaveTimer.current) {
      clearTimeout(autosaveTimer.current);
      autosaveTimer.current = null;
    }
    if (skipSave.current) {
      skipSave.current = false;
      setEditingId(null);
      return;
    }
    const nextText = draft.trim();
    if (
      nextText !== "" &&
      nextText !== segments[index].text &&
      nextText !== lastAutosaved.current
    ) {
      lastAutosaved.current = nextText;
      onEditSegment(index, nextText, false);
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

  const pct = seconds > 0 ? Math.min(100, (current / seconds) * 100) : 0;
  const lowConfidenceCount = useMemo(
    () => segments.filter((s) => (s.confidence ?? 1) < 0.85).length,
    [segments],
  );

  const visibleSegments = useMemo(() => {
    const q = segSearch.trim().toLowerCase();
    return segments
      .map((s, originalIndex) => ({ segment: s, originalIndex }))
      .filter(({ segment }) => {
        if (onlyLowConf && (segment.confidence ?? 1) >= 0.85) return false;
        if (speakerFilter !== "ALL" && segment.speaker !== speakerFilter) return false;
        if (q !== "" && !`${segment.text} ${segment.speaker}`.toLowerCase().includes(q)) {
          return false;
        }
        return true;
      });
  }, [onlyLowConf, segSearch, segments, speakerFilter]);

  const saveLabel = useMemo(() => {
    if (!canRead) return status.note;
    if (saveStatus === "saving") return "Menyimpan perubahan otomatis…";
    if (saveStatus === "saved") return "Semua perubahan tersimpan otomatis";
    if (saveStatus === "conflict") return "Konflik versi — transkrip telah dimuat ulang";
    if (saveStatus === "error") return "Gagal menyimpan — periksa koneksi";
    return "Simpan otomatis aktif (≤2 detik)";
  }, [canRead, saveStatus, status.note]);

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
            {lowConfidenceCount > 0 ? <span className="tab-count">{lowConfidenceCount}</span> : null}
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
          <button
            className="icon-btn"
            onClick={() => setConfirmDelete((v) => !v)}
            title="Hapus job ini"
            aria-label="Hapus job ini"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>

      {confirmDelete ? (
        <div className="inline-delete-bar" role="alert">
          <span>Hapus job “{job.title}” beserta audio dan transkripnya?</span>
          <div className="inline-delete-actions">
            <button
              className="btn btn-danger btn-sm"
              onClick={() => {
                setConfirmDelete(false);
                onDeleteJob(job.id);
              }}
            >
              <Trash2 size={13} /> Ya, hapus
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => setConfirmDelete(false)}>
              Batal
            </button>
          </div>
        </div>
      ) : null}

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
            {job.diarized && speakers.length > 0
              ? speakers.map((s) => s.name).join(" · ")
              : "Pelabelan pembicara tidak aktif"}
          </span>
          <span className="retention-badge" title="Batas penyimpanan audio">
            <Lock size={11} /> {audioAvailable ? `Audio ${job.audioExpires ?? "≤24 jam"}` : "Audio sudah dihapus"}
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
          <button
            className="player-step-btn"
            onClick={() => seek(current - 5, false)}
            disabled={!audioAvailable}
            title="Mundur 5 detik"
            aria-label="Mundur 5 detik"
          >
            <Rewind size={13} />
          </button>
          <button
            className="player-step-btn"
            onClick={() => seek(current + 5, false)}
            disabled={!audioAvailable}
            title="Maju 5 detik"
            aria-label="Maju 5 detik"
          >
            <FastForward size={13} />
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
          <button
            type="button"
            className="player-speed-btn"
            onClick={cycleSpeed}
            disabled={!audioAvailable}
            title="Kecepatan putar"
          >
            {speed}×
          </button>
          <span className="player-note">
            {audioAvailable ? (
              <>sisa {job.audioExpires ?? "≤24 jam"}</>
            ) : (
              <>
                <Lock size={12} /> audio dihapus otomatis
              </>
            )}
          </span>
        </div>
      ) : null}

      {canRead && tab === "transcript" ? (
        <div className="transcript-filter-bar">
          <div className="seg-search-box">
            <Search size={13} />
            <input
              type="text"
              value={segSearch}
              onChange={(e) => setSegSearch(e.target.value)}
              placeholder="Cari kata di dalam transkrip…"
              aria-label="Cari kata di dalam transkrip"
            />
            {segSearch ? (
              <button type="button" onClick={() => setSegSearch("")} aria-label="Hapus pencarian">
                <X size={12} />
              </button>
            ) : null}
          </div>
          {speakers.length > 1 ? (
            <select
              className="seg-speaker-filter"
              value={speakerFilter}
              onChange={(e) => setSpeakerFilter(e.target.value)}
              aria-label="Filter pembicara"
            >
              <option value="ALL">Semua pembicara</option>
              {speakers.map((sp) => (
                <option key={sp.name} value={sp.name}>
                  {sp.name}
                </option>
              ))}
            </select>
          ) : null}
          {lowConfidenceCount > 0 ? (
            <button
              type="button"
              className={`low-conf-filter-btn ${onlyLowConf ? "is-active" : ""}`}
              onClick={() => setOnlyLowConf((v) => !v)}
              title="Tampilkan hanya segmen berkeyakinan rendah (<85%)"
            >
              <Filter size={11} />
              <span>Perlu cek ({lowConfidenceCount})</span>
            </button>
          ) : null}
        </div>
      ) : null}

      <div className={`transcript-body ${canRead ? "" : "is-state"}`}>
        {!canRead ? (
          <StatusBody job={job} onNavigate={onNavigate} onDeleteJob={onDeleteJob} onToast={onToast} />
        ) : null}

        {canRead && tab === "transcript" ? (
          <div className="segments">
            {visibleSegments.map(({ segment: s, originalIndex: i }) => {
              const currentSeg = i === activeIndex && (playing || current > 0);
              const editing = editingId === i;
              const isLowConf = (s.confidence ?? 1) < 0.85;
              return (
                <article
                  key={`${s.start}-${i}`}
                  className={`segment ${currentSeg ? "is-current" : ""} ${
                    editing ? "is-editing" : ""
                  } ${isLowConf ? "is-low-conf" : ""}`}
                  style={{ "--delay": `${Math.min(i, 6) * 40}ms` } as CSSProperties}
                  onClick={(e) => {
                    if ((e.target as HTMLElement).closest("button, select, textarea, input, a, label")) return;
                    seek(s.start || 0);
                  }}
                  title="Klik segmen untuk memutar audio dari titik ini"
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
                      {s.role ? <span className="segment-role">{s.role}</span> : null}
                      <button className="segment-time" onClick={() => seek(s.start || 0)}>
                        {s.time}
                      </button>
                      {s.edited ? <span className="edit-badge">diedit</span> : null}
                      {isLowConf ? (
                        <span
                          className="low-conf"
                          title={`Model kurang yakin (${Math.round((s.confidence ?? 0) * 100)}%). Klik pensil untuk menyunting.`}
                        >
                          <AlertTriangle size={10} /> perlu cek ({Math.round((s.confidence ?? 0) * 100)}%)
                        </span>
                      ) : null}
                      <div className="segment-tools">
                        {speakers.length > 0 ? (
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
                        ) : null}
                        <button
                          className="seg-edit"
                          onClick={() => startEdit(i)}
                          aria-label={`Edit segmen ${i + 1}`}
                          title="Sunting teks segmen"
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
                          <span>Simpan otomatis ≤2 dtk · Enter selesai · Esc batal</span>
                          <button className="btn btn-primary btn-xs" onClick={() => saveEdit(i)}>
                            <Check size={12} /> Selesai
                          </button>
                        </div>
                      </div>
                    ) : (
                      <p onDoubleClick={() => startEdit(i)}>{s.text}</p>
                    )}
                  </div>
                </article>
              );
            })}

            {visibleSegments.length === 0 ? (
              <div className="empty-actions">
                <p>Tidak ada segmen yang cocok dengan filter saat ini.</p>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => {
                    setSegSearch("");
                    setOnlyLowConf(false);
                    setSpeakerFilter("ALL");
                  }}
                >
                  Reset filter segmen
                </button>
              </div>
            ) : null}
          </div>
        ) : null}

        {canRead && tab === "speakers" ? (
          <div className="speakers-tab">
            <div className="panel-inline-head">
              <div>
                <h3>Label pembicara</h3>
                <p>Berlaku untuk transkrip ini saja, tidak lintas rekaman.</p>
              </div>
              <span className="pill-soft">
                <Users size={11} /> maks 8
              </span>
            </div>

            {!job.diarized || speakers.length === 0 ? (
              <div className="inline-notice">
                <UserRound size={16} />
                <p>
                  Pelabelan pembicara tidak aktif atau hanya satu pembicara terdeteksi pada job ini.
                  Aktifkan sakelar <b>Pelabelan pembicara</b> saat merekam/mengunggah untuk memisahkan
                  pembicara (2× kuota).
                </p>
                <button className="btn btn-ghost btn-sm" onClick={() => onNavigate("home")}>
                  Buat job berlabel
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
                Ketik nama baru di atas lalu tekan Enter untuk mengganti semua segmen berlabel
                tersebut. Untuk memindahkan satu segmen saja, gunakan dropdown di kanan segmen pada
                tab Transkrip.
              </span>
            </div>
          </div>
        ) : null}

        {canRead && tab === "export" ? (
          <div className="export-tab">
            <div className="panel-inline-head">
              <div>
                <h3>Ekspor & kelola transkrip</h3>
                <p>Ekspor mencerminkan suntingan dan nama pembicara terbaru, walau audio sudah dihapus.</p>
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

            <div className="danger-row">
              <div>
                <b>Hapus job ini sekarang</b>
                <p>Audio dan seluruh segmen transkrip untuk job ini langsung dihapus permanen.</p>
              </div>
              <button className="btn btn-danger btn-sm" onClick={() => setConfirmDelete(true)}>
                <Trash2 size={13} /> Hapus job
              </button>
            </div>

            <div className="export-note">
              <Lock size={13} />
              <span>
                Audio dihapus otomatis ≤ 24 jam setelah job selesai. Transkrip tersimpan 30 hari di
                sesi peramban ini.
              </span>
            </div>
          </div>
        ) : null}
      </div>

      <div className="transcript-foot">
        <span>
          <span
            className={`foot-dot ${
              !canRead ? "is-idle" : saveStatus === "saving" ? "is-saving" : ""
            }`}
          />
          {saveLabel}
        </span>
        <span className="foot-model">
          <Globe2 size={12} /> {job.model ?? "whisper-large-v3-turbo"}
          {canRead ? ` · ${(job.words ?? 0).toLocaleString("id-ID")} kata` : ""}
        </span>
      </div>
    </section>
  );
}
