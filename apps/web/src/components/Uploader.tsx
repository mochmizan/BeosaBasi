import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Clock,
  Download,
  FileAudio,
  FileUp,
  FolderUp,
  Globe2,
  Loader2,
  Mic,
  Minus,
  Pause,
  Play,
  Plus,
  RotateCcw,
  Send,
  Square,
  Timer,
  Trash2,
  TriangleAlert,
  Users,
  WifiOff,
  X,
} from "lucide-react";
import { STAGE, STAGE_ORDER, downloadBlob, formatClock, probeAudioDuration } from "../lib/ui";
import type { InputMode, QuotaView, StudioPrefs, UploadFileMeta, UploadState } from "./studio";

const ACCEPT = ".mp3,.m4a,.wav,.flac,.ogg,.opus,.mp4,.webm,audio/*,video/mp4,video/webm";
const MAX_MB = 200;
const MAX_MINUTES = 90;
const FORMATS = ["MP3", "M4A", "WAV", "FLAC", "OGG", "OPUS", "MP4", "WEBM"];

const LANGUAGES: { value: UploadFileMeta["language"]; label: string }[] = [
  { value: "id", label: "Bahasa Indonesia" },
  { value: "en", label: "English" },
  { value: "auto", label: "Deteksi otomatis" },
];

const MIME_CANDIDATES: { mime: string; ext: string }[] = [
  { mime: "audio/webm;codecs=opus", ext: "webm" },
  { mime: "audio/webm", ext: "webm" },
  { mime: "audio/ogg;codecs=opus", ext: "ogg" },
  { mime: "audio/mp4", ext: "m4a" },
];

function pickRecorderMime(): { mime: string; ext: string } {
  if (typeof MediaRecorder !== "undefined" && typeof MediaRecorder.isTypeSupported === "function") {
    for (const candidate of MIME_CANDIDATES) {
      if (MediaRecorder.isTypeSupported(candidate.mime)) {
        return candidate;
      }
    }
  }
  return { mime: "audio/webm", ext: "webm" };
}

function defaultRecordingBaseName(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `rekaman-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}`;
}

function StageList({
  stage,
  progress,
  diarized,
}: {
  stage: string | null;
  progress: number;
  diarized: boolean;
}) {
  const activeIndex = stage ? STAGE_ORDER.indexOf(stage as (typeof STAGE_ORDER)[number]) : -1;
  return (
    <ol className="stage-list" aria-label="Tahap pemrosesan">
      {STAGE_ORDER.map((key, i) => {
        const skipped = key === "diarizing" && !diarized;
        const done = !skipped && (i < activeIndex || progress >= 100);
        const current = !skipped && i === activeIndex && progress < 100;
        return (
          <li
            key={key}
            className={`stage-item ${done ? "is-done" : ""} ${current ? "is-current" : ""} ${
              skipped ? "is-skipped" : ""
            }`}
          >
            <span className="stage-dot">
              {done ? <CheckCircle2 size={12} /> : current ? <Loader2 size={12} className="spin" /> : null}
            </span>
            <span>{STAGE[key].short}</span>
          </li>
        );
      })}
    </ol>
  );
}

function StatusCard({
  upload,
  workerOnline,
  onCancel,
  onResume,
  onOpenJob,
  onRefreshWorker,
}: {
  upload: UploadState;
  workerOnline: boolean;
  onCancel: (force?: boolean) => void;
  onResume: () => void;
  onOpenJob: (id: string) => void;
  onRefreshWorker: () => void;
}) {
  const {
    phase,
    progress,
    partsDone,
    partsTotal,
    fileMeta,
    stage,
    jobId,
    queuePosition,
    eta,
    canResume,
    error,
  } = upload;

  if (phase === "uploading") {
    const chunkInfo =
      partsTotal && partsTotal > 1 ? ` · potongan ${partsDone ?? 0}/${partsTotal} (3× paralel)` : "";
    return (
      <div className="upload-status is-uploading">
        <div className="status-top">
          <span className="status-icon">
            <FileUp size={19} />
          </span>
          <div className="status-copy">
            <b>Mengunggah “{fileMeta?.name}”</b>
            <span>
              {fileMeta?.sizeMb} MB
              {fileMeta?.durationSec ? ` · ${formatClock(fileMeta.durationSec)}` : ""}
              {chunkInfo}
            </span>
          </div>
          <span className="status-percent">{Math.round(progress)}%</span>
        </div>
        <div className="status-bar">
          <i style={{ width: `${progress}%` }} />
        </div>
        <div className="status-foot">
          <span>Berkas dikirim terenkripsi ke penyimpanan sementara.</span>
          <button className="link-btn" onClick={() => onCancel()}>
            <X size={12} /> Batalkan
          </button>
        </div>
      </div>
    );
  }

  if (phase === "queued") {
    const pos = queuePosition ?? 1;
    const est = eta ?? "±2 menit";
    return (
      <div className="upload-status is-queued">
        <div className="status-top">
          <span className="status-icon">
            <Timer size={19} />
          </span>
          <div className="status-copy">
            <b>{workerOnline ? "Menunggu giliran antrean" : "Pemrosesan tertunda"}</b>
            <span>
              {fileMeta?.name} · {fileMeta?.sizeMb} MB
            </span>
          </div>
          <span className="queue-pill">#{pos}</span>
        </div>
        <div className="queue-grid">
          <div>
            <span>Posisi antrean</span>
            <b>#{pos}</b>
          </div>
          <div>
            <span>Perkiraan mulai</span>
            <b>{workerOnline ? est : "Menunggu pekerja"}</b>
          </div>
          <div>
            <span>Pelabelan</span>
            <b>
              {fileMeta?.diarized
                ? `Aktif · ${fileMeta.speakers} pembicara · 2× kuota`
                : "Mati (1× kuota)"}
            </b>
          </div>
        </div>
        {!workerOnline ? (
          <div className="offline-note">
            <WifiOff size={16} />
            <p>
              <b>Perangkat pekerja GPU sedang tidak aktif.</b> Job kamu sudah tersimpan aman di
              antrean dan akan otomatis diproses saat perangkat aktif.
            </p>
            <button className="btn btn-ghost btn-sm" onClick={onRefreshWorker}>
              Periksa pekerja
            </button>
          </div>
        ) : null}
        <div className="status-foot">
          <span>Audio dihapus otomatis ≤ 24 jam setelah selesai.</span>
          <button className="link-btn is-danger" onClick={() => onCancel()}>
            <X size={12} /> Batalkan job
          </button>
        </div>
      </div>
    );
  }

  if (phase === "processing") {
    return (
      <div className="upload-status is-processing">
        <div className="status-top">
          <span className="status-icon">
            <Loader2 size={19} className="spin" />
          </span>
          <div className="status-copy">
            <b>{stage ? STAGE[stage]?.label ?? "Memproses audio" : "Memproses audio"}</b>
            <span>{fileMeta?.name} · Whisper large-v3-turbo</span>
          </div>
          <span className="status-percent">{Math.round(progress)}%</span>
        </div>
        <div className="status-bar">
          <i style={{ width: `${progress}%` }} />
        </div>
        <StageList stage={stage} progress={progress} diarized={Boolean(fileMeta?.diarized)} />
        <div className="status-foot">
          <span>Kamu boleh menutup tab ini. Job tetap berjalan di server.</span>
          <button className="link-btn is-danger" onClick={() => onCancel()}>
            <X size={12} /> Batalkan job
          </button>
        </div>
      </div>
    );
  }

  if (phase === "completed") {
    return (
      <div className="upload-status is-done">
        <div className="status-top">
          <span className="status-icon">
            <CheckCircle2 size={19} />
          </span>
          <div className="status-copy">
            <b>Transkrip siap disunting</b>
            <span>
              {fileMeta?.name} · {fileMeta?.sizeMb} MB selesai diproses
            </span>
          </div>
          <span className="done-pill">Selesai</span>
        </div>
        <div className="done-actions">
          <button
            className="btn btn-primary btn-sm"
            onClick={() => {
              if (jobId) onOpenJob(jobId);
            }}
          >
            Buka halaman penuh <ArrowRight size={14} />
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => onCancel(true)}>
            <RotateCcw size={14} /> Transkripsi baru
          </button>
        </div>
        <p className="done-note">Audio akan dihapus otomatis dalam 24 jam. Transkrip tersimpan 30 hari.</p>
      </div>
    );
  }

  if (phase === "failed") {
    return (
      <div className="upload-status is-failed">
        <div className="status-top">
          <span className="status-icon">
            <TriangleAlert size={19} />
          </span>
          <div className="status-copy">
            <b>Unggahan atau pemrosesan gagal</b>
            <span>{error ?? "Berkas tidak bisa diproses."}</span>
          </div>
        </div>
        <div className="done-actions">
          {canResume ? (
            <button className="btn btn-primary btn-sm" onClick={onResume}>
              <RotateCcw size={14} /> Lanjutkan unggahan
            </button>
          ) : null}
          <button className="btn btn-ghost btn-sm" onClick={() => onCancel(true)}>
            <X size={14} /> Mulai baru
          </button>
        </div>
      </div>
    );
  }

  return null;
}

export default function Uploader({
  upload,
  quota,
  prefs,
  inputMode,
  onChangeMode,
  workerOnline,
  onRefreshWorker,
  onPickFile,
  onResumeUpload,
  onCancelUpload,
  onOpenJob,
  onToast,
}: {
  upload: UploadState;
  quota: QuotaView;
  prefs: StudioPrefs;
  inputMode: InputMode;
  onChangeMode: (mode: InputMode) => void;
  workerOnline: boolean;
  onRefreshWorker: () => void;
  onPickFile: (file: File, meta: UploadFileMeta) => void;
  onResumeUpload: () => void;
  onCancelUpload: (force?: boolean) => void;
  onOpenJob: (id: string) => void;
  onToast: (message: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [language, setLanguage] = useState<UploadFileMeta["language"]>(prefs.defaultLanguage);
  const [diarized, setDiarized] = useState(prefs.defaultDiarization);
  const [speakerCount, setSpeakerCount] = useState(prefs.defaultSpeakers);

  // State perekam suara web (MediaRecorder + Web Audio Analyser)
  const [recPhase, setRecPhase] = useState<"idle" | "recording" | "paused" | "recorded">("idle");
  const [recSeconds, setRecSeconds] = useState(0);
  const [recBlob, setRecBlob] = useState<Blob | null>(null);
  const [recExt, setRecExt] = useState("webm");
  const [recMime, setRecMime] = useState("audio/webm");
  const [recTitle, setRecTitle] = useState(defaultRecordingBaseName);
  const [recPreviewUrl, setRecPreviewUrl] = useState<string | null>(null);
  const [recError, setRecError] = useState<string | null>(null);
  const [liveBars, setLiveBars] = useState<number[]>(() => Array.from({ length: 36 }, () => 0.18));

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    setLanguage(prefs.defaultLanguage);
    setDiarized(prefs.defaultDiarization);
    setSpeakerCount(prefs.defaultSpeakers);
  }, [prefs.defaultDiarization, prefs.defaultLanguage, prefs.defaultSpeakers]);

  const cleanupMedia = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (animFrameRef.current !== null) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (audioCtxRef.current) {
      void audioCtxRef.current.close().catch(() => undefined);
      audioCtxRef.current = null;
    }
    mediaRecorderRef.current = null;
  }, []);

  useEffect(() => {
    return () => {
      cleanupMedia();
    };
  }, [cleanupMedia]);

  useEffect(() => {
    return () => {
      if (recPreviewUrl) URL.revokeObjectURL(recPreviewUrl);
    };
  }, [recPreviewUrl]);

  const busy = ["uploading", "queued", "processing"].includes(upload.phase);

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    const ext = file.name.split(".").pop()?.toUpperCase() ?? "";
    if (!FORMATS.includes(ext)) {
      onToast(`Format .${ext.toLowerCase()} belum didukung. Pakai ${FORMATS.join(", ")}.`);
      return;
    }
    if (file.size <= 0) {
      onToast("Berkas kosong dan tidak bisa diunggah.");
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      onToast(`Berkas ${Math.round(file.size / 1024 / 1024)} MB melebihi batas 200 MB.`);
      return;
    }

    const durationSec = await probeAudioDuration(file);
    if (durationSec !== null && durationSec > MAX_MINUTES * 60) {
      onToast(`Durasi audio (${Math.round(durationSec / 60)} menit) melebihi batas 90 menit.`);
      return;
    }

    const estMinutes = durationSec ? (durationSec / 60) * (diarized ? 2 : 1) : 0;
    const remaining = Math.max(0, quota.minutes - quota.used);
    if (remaining <= 0) {
      onToast(`Kuota hari ini habis. Kuota pulih pada ${quota.reset}.`);
      return;
    }
    if (estMinutes > 0 && estMinutes > remaining + 5) {
      onToast(
        `Perhatian: estimasi pemakaian (±${Math.ceil(estMinutes)} mnt) mendekati/melebihi sisa kuota (${remaining} mnt).`,
      );
    }

    onPickFile(file, {
      name: file.name,
      sizeMb: Math.max(0.1, Math.round((file.size / 1024 / 1024) * 10) / 10),
      durationSec: durationSec ?? undefined,
      diarized,
      speakers: diarized ? speakerCount : 1,
      language,
      source: "upload",
    });
  };

  // ---- Logika Perekam Suara Web ------------------------------------------

  const startVisualizer = (stream: MediaStream) => {
    try {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      audioCtxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 128;
      source.connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);

      const tick = () => {
        analyser.getByteFrequencyData(data);
        const bars = Array.from({ length: 36 }, (_, i) => {
          const val = data[i % data.length] ?? 0;
          return Math.max(0.12, Math.min(1, val / 220));
        });
        setLiveBars(bars);
        animFrameRef.current = requestAnimationFrame(tick);
      };
      animFrameRef.current = requestAnimationFrame(tick);
    } catch {
      // Abaikan bila Web Audio API dibatasi
    }
  };

  const startRecording = async () => {
    setRecError(null);
    if (
      typeof navigator === "undefined" ||
      !navigator.mediaDevices ||
      typeof navigator.mediaDevices.getUserMedia !== "function" ||
      typeof MediaRecorder === "undefined"
    ) {
      const msg = "Peramban ini belum mendukung perekaman mikrofon langsung. Gunakan unggah berkas.";
      setRecError(msg);
      onToast(msg);
      return;
    }

    const remaining = Math.max(0, quota.minutes - quota.used);
    if (remaining <= 0) {
      onToast(`Kuota hari ini habis. Kuota pulih pada ${quota.reset}.`);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      const chosen = pickRecorderMime();
      setRecExt(chosen.ext);
      setRecMime(chosen.mime.split(";", 1)[0]);

      let recorder: MediaRecorder;
      try {
        recorder = new MediaRecorder(stream, { mimeType: chosen.mime });
      } catch {
        recorder = new MediaRecorder(stream);
      }

      chunksRef.current = [];
      recorder.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) {
          chunksRef.current.push(ev.data);
        }
      };

      recorder.onstop = () => {
        const finalMime = (recorder.mimeType || chosen.mime).split(";", 1)[0] || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: finalMime });
        cleanupMedia();
        if (blob.size <= 0) {
          setRecError("Rekaman kosong. Pastikan mikrofon aktif lalu coba lagi.");
          setRecPhase("idle");
          return;
        }
        if (recPreviewUrl) URL.revokeObjectURL(recPreviewUrl);
        const url = URL.createObjectURL(blob);
        setRecBlob(blob);
        setRecMime(finalMime);
        setRecPreviewUrl(url);
        setRecTitle(defaultRecordingBaseName());
        setRecPhase("recorded");
      };

      mediaRecorderRef.current = recorder;
      recorder.start(500);
      setRecSeconds(0);
      setRecPhase("recording");
      startVisualizer(stream);

      timerRef.current = setInterval(() => {
        setRecSeconds((prev) => {
          const next = prev + 1;
          if (next >= MAX_MINUTES * 60) {
            recorder.stop();
          }
          return next;
        });
      }, 1000);
    } catch {
      cleanupMedia();
      const msg = "Izin mikrofon ditolak atau perangkat mikrofon tidak ditemukan.";
      setRecError(msg);
      onToast(msg);
    }
  };

  const pauseOrResumeRecording = () => {
    const rec = mediaRecorderRef.current;
    if (!rec) return;
    if (rec.state === "recording") {
      rec.pause();
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      setRecPhase("paused");
    } else if (rec.state === "paused") {
      rec.resume();
      timerRef.current = setInterval(() => {
        setRecSeconds((prev) => prev + 1);
      }, 1000);
      setRecPhase("recording");
    }
  };

  const stopRecording = () => {
    const rec = mediaRecorderRef.current;
    if (rec && rec.state !== "inactive") {
      rec.stop();
    } else {
      cleanupMedia();
      setRecPhase("idle");
    }
  };

  const discardRecording = () => {
    cleanupMedia();
    if (recPreviewUrl) URL.revokeObjectURL(recPreviewUrl);
    setRecBlob(null);
    setRecPreviewUrl(null);
    setRecSeconds(0);
    setRecError(null);
    setRecPhase("idle");
  };

  const submitRecording = () => {
    if (!recBlob) return;
    const cleanBase =
      recTitle
        .trim()
        .replace(/\.[^.]+$/, "")
        .replace(/[^\w\s-]/g, "")
        .replace(/\s+/g, "-") || defaultRecordingBaseName();
    const filename = `${cleanBase}.${recExt}`;
    const file = new File([recBlob], filename, { type: recMime });
    const sizeMb = Math.max(0.1, Math.round((file.size / 1024 / 1024) * 10) / 10);

    onPickFile(file, {
      name: filename,
      sizeMb,
      durationSec: Math.max(1, recSeconds),
      diarized,
      speakers: diarized ? speakerCount : 1,
      language,
      source: "record",
    });
    discardRecording();
  };

  const downloadRecordingLocally = () => {
    if (!recBlob) return;
    const cleanBase =
      recTitle
        .trim()
        .replace(/\.[^.]+$/, "")
        .replace(/[^\w\s-]/g, "")
        .replace(/\s+/g, "-") || defaultRecordingBaseName();
    downloadBlob(`${cleanBase}.${recExt}`, recBlob);
    onToast("Rekaman disimpan ke perangkat kamu");
  };

  const used = quota.used;
  const total = quota.minutes;
  const percent = Math.min(100, Math.round((used / total) * 100));

  return (
    <section
      className={`panel upload-panel ${
        recPhase === "recording" ? "phase-recording" : recPhase === "recorded" ? "phase-done" : ""
      }`}
    >
      <div className="upload-glow" />
      <div className="upload-head">
        <div className="upload-title">
          <span className="upload-icon">
            {inputMode === "record" ? <Mic size={16} /> : <FolderUp size={16} />}
          </span>
          <div>
            <b>{inputMode === "record" ? "Rekam suara langsung" : "Unggah berkas audio"}</b>
            <span>
              {inputMode === "record"
                ? "Mikrofon peramban · langsung ditranskripsi tanpa unggah manual"
                : FORMATS.join(" · ")}
            </span>
          </div>
        </div>
        <button
          className={`worker-chip ${workerOnline ? "is-online" : "is-offline"}`}
          onClick={onRefreshWorker}
          title="Klik untuk memeriksa status pekerja"
        >
          <i /> {workerOnline ? "Pekerja online" : "Pekerja tertunda"}
        </button>
      </div>

      {/* Pemilih Mode: Rekam Suara vs Unggah Berkas */}
      {upload.phase === "idle" ? (
        <div className="input-mode-tabs" role="tablist" aria-label="Metode masukan suara">
          <button
            type="button"
            role="tab"
            aria-selected={inputMode === "record"}
            className={`input-mode-tab ${inputMode === "record" ? "is-active" : ""}`}
            onClick={() => onChangeMode("record")}
          >
            <Mic size={14} />
            <span>Rekam suara</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={inputMode === "upload"}
            className={`input-mode-tab ${inputMode === "upload" ? "is-active" : ""}`}
            onClick={() => {
              if (recPhase === "recording" || recPhase === "paused") {
                stopRecording();
              }
              onChangeMode("upload");
            }}
          >
            <FileUp size={14} />
            <span>Unggah berkas</span>
          </button>
        </div>
      ) : null}

      {upload.phase !== "idle" ? (
        <StatusCard
          upload={upload}
          workerOnline={workerOnline}
          onCancel={onCancelUpload}
          onResume={onResumeUpload}
          onOpenJob={onOpenJob}
          onRefreshWorker={onRefreshWorker}
        />
      ) : inputMode === "record" ? (
        <div className="recorder-box">
          {recPhase === "idle" || recPhase === "recording" || recPhase === "paused" ? (
            <>
              <div className="rec-status-bar">
                <span
                  className={`status-dot ${
                    recPhase === "recording" ? "recording" : recPhase === "paused" ? "processing" : ""
                  }`}
                />
                <span>
                  {recPhase === "recording"
                    ? "Merekam suara dari mikrofon…"
                    : recPhase === "paused"
                      ? "Rekaman dijeda"
                      : "Siap merekam dari mikrofon"}
                </span>
                {recPhase === "recording" ? <span className="live-badge">LIVE</span> : null}
              </div>

              <div className="orb-stage">
                <div className="orb-glow" />
                <div className="orb-rings" aria-hidden="true">
                  <i />
                  <i />
                  <i />
                </div>
                <button
                  type="button"
                  className="orb"
                  onClick={() => {
                    if (recPhase === "idle") void startRecording();
                    else stopRecording();
                  }}
                  aria-label={recPhase === "idle" ? "Mulai rekam suara" : "Hentikan rekaman"}
                >
                  <span className="orb-sheen" />
                  {recPhase === "idle" ? <Mic size={36} /> : <Square size={30} fill="currentColor" />}
                </button>
              </div>

              <div className="timer" aria-live="polite">
                {formatClock(recSeconds)}
              </div>

              <p className="orb-hint">
                {recPhase === "idle"
                  ? "Klik tombol mikrofon untuk merekam rapat, wawancara, atau catatan suara langsung di browser."
                  : "Bicara jelas ke mikrofon. Klik kotak berhenti saat selesai untuk meninjau atau mengirim."}
              </p>

              <div
                className={`waveform rec-wave ${recPhase === "recording" ? "is-active" : ""}`}
                style={{ height: 38 }}
                aria-hidden="true"
              >
                {liveBars.map((h, i) => (
                  <span
                    key={i}
                    style={
                      {
                        "--h": recPhase === "recording" ? h : 0.2 + ((i * 7) % 10) * 0.04,
                        "--dur": `${0.5 + (i % 5) * 0.1}s`,
                        "--delay": `${(i % 7) * 0.05}s`,
                      } as CSSProperties
                    }
                  />
                ))}
              </div>

              {recError ? (
                <div className="rec-error-banner" role="alert">
                  <TriangleAlert size={14} />
                  <span>{recError}</span>
                </div>
              ) : null}

              <div className="rec-controls">
                {recPhase === "idle" ? (
                  <>
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => void startRecording()}
                    >
                      <Mic size={15} /> Mulai rekam
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      onClick={() => onChangeMode("upload")}
                    >
                      <FileUp size={15} /> Pilih berkas saja
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      onClick={pauseOrResumeRecording}
                    >
                      {recPhase === "paused" ? <Play size={15} /> : <Pause size={15} />}
                      {recPhase === "paused" ? "Lanjutkan" : "Jeda"}
                    </button>
                    <button type="button" className="btn btn-stop" onClick={stopRecording}>
                      <span className="stop-square" /> Selesai & tinjau
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger"
                      onClick={discardRecording}
                      title="Buang rekaman"
                    >
                      <Trash2 size={14} /> Batal
                    </button>
                  </>
                )}
              </div>
            </>
          ) : (
            <div className="recorded-review">
              <div className="recorded-head">
                <span className="status-icon">
                  <CheckCircle2 size={19} />
                </span>
                <div className="status-copy">
                  <b>Rekaman selesai ({formatClock(recSeconds)})</b>
                  <span>
                    {recBlob ? `${Math.max(0.1, Math.round((recBlob.size / 1024 / 1024) * 10) / 10)} MB` : ""} ·{" "}
                    {recExt.toUpperCase()} siap ditranskripsi
                  </span>
                </div>
              </div>

              <label className="recorded-title-field">
                <span>Judul rekaman</span>
                <input
                  type="text"
                  value={recTitle}
                  onChange={(e) => setRecTitle(e.target.value)}
                  placeholder="Nama rekaman…"
                  aria-label="Judul rekaman"
                />
              </label>

              {recPreviewUrl ? (
                <audio
                  controls
                  src={recPreviewUrl}
                  className="recorded-audio-preview"
                  preload="metadata"
                />
              ) : null}

              <div className="recorded-actions">
                <button type="button" className="btn btn-primary" onClick={submitRecording}>
                  <Send size={15} /> Transkripsikan sekarang
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={downloadRecordingLocally}
                >
                  <Download size={14} /> Simpan audio
                </button>
                <button type="button" className="btn btn-danger" onClick={discardRecording}>
                  <RotateCcw size={14} /> Rekam ulang
                </button>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div
          className={`dropzone ${dragging ? "is-drag" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            void handleFile(e.dataTransfer.files?.[0]);
          }}
        >
          <span className="drop-rings" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span className="drop-icon">
            <FileAudio size={26} />
          </span>
          <b>Tarik berkas audio/video ke sini</b>
          <p>
            atau pilih dari perangkat. Maksimal <strong>200 MB</strong> dan <strong>90 menit</strong>{" "}
            per berkas, atau langsung rekam dari mikrofon.
          </p>
          <div className="drop-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => inputRef.current?.click()}
            >
              <FileUp size={15} /> Pilih berkas
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => onChangeMode("record")}
            >
              <Mic size={15} /> Rekam suara
            </button>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            hidden
            onChange={(e) => {
              void handleFile(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
        </div>
      )}

      <div className="upload-options">
        <label className="upload-field">
          <span>Bahasa audio</span>
          <div className="select-wrap">
            <Globe2 size={14} />
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value as UploadFileMeta["language"])}
              disabled={busy}
            >
              {LANGUAGES.map((l) => (
                <option key={l.value} value={l.value}>
                  {l.label}
                </option>
              ))}
            </select>
          </div>
        </label>

        <div className="diarize-row">
          <div className="diarize-copy">
            <b>
              <Users size={13} /> Pelabelan pembicara
            </b>
            <p>Pisahkan pembicara · maks 8 orang · 2× kuota</p>
          </div>
          <button
            type="button"
            className={`switch ${diarized ? "is-on" : ""}`}
            onClick={() => setDiarized((v) => !v)}
            role="switch"
            aria-checked={diarized}
            aria-label="Pelabelan pembicara"
            disabled={busy}
          >
            <i />
          </button>
        </div>

        {diarized ? (
          <div className="speaker-estimate">
            <div className="speaker-estimate-copy">
              <label htmlFor="speaker-estimate">Perkiraan jumlah pembicara</label>
              <span>Bantu akurasi pelabelan · 2–8 orang</span>
            </div>
            <div className="speaker-stepper">
              <button
                type="button"
                onClick={() => setSpeakerCount((count) => Math.max(2, count - 1))}
                disabled={busy || speakerCount <= 2}
                aria-label="Kurangi perkiraan pembicara"
              >
                <Minus size={13} />
              </button>
              <input
                id="speaker-estimate"
                type="number"
                min="2"
                max="8"
                value={speakerCount}
                disabled={busy}
                onChange={(e) =>
                  setSpeakerCount(Math.min(8, Math.max(2, Number(e.target.value) || 2)))
                }
              />
              <button
                type="button"
                onClick={() => setSpeakerCount((count) => Math.min(8, count + 1))}
                disabled={busy || speakerCount >= 8}
                aria-label="Tambah perkiraan pembicara"
              >
                <Plus size={13} />
              </button>
            </div>
          </div>
        ) : null}
      </div>

      <div className="quota-strip">
        <div className="quota-row">
          <span>
            <Clock size={13} /> Kuota hari ini
          </span>
          <b>
            {used} / {total} menit
          </b>
        </div>
        <div className="quota-bar">
          <i style={{ width: `${percent}%` }} />
        </div>
        <p>
          Reset {quota.reset} · {quota.active}/{quota.maxActive} job berjalan · audio dihapus ≤24 jam
          {diarized ? " · diarisasi 2× kuota" : ""}
        </p>
      </div>
    </section>
  );
}
