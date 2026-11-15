import { useRef, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Clock,
  FileAudio,
  FileUp,
  FolderUp,
  Globe2,
  Loader2,
  Minus,
  Plus,
  RotateCcw,
  ShieldCheck,
  Timer,
  TriangleAlert,
  Users,
  WifiOff,
  X,
} from "lucide-react";
import { STAGE, STAGE_ORDER } from "../lib/ui";
import type { QuotaView, UploadFileMeta, UploadState } from "./studio";

const ACCEPT = ".mp3,.m4a,.wav,.flac,.ogg,.opus,.mp4,.webm,audio/*,video/mp4,video/webm";
const MAX_MB = 200;
const FORMATS = ["MP3", "M4A", "WAV", "FLAC", "OGG", "OPUS", "MP4", "WEBM"];

const LANGUAGES: { value: UploadFileMeta["language"]; label: string }[] = [
  { value: "id", label: "Bahasa Indonesia" },
  { value: "en", label: "English" },
  { value: "auto", label: "Deteksi otomatis" },
];

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
  onOpenJob,
  onRefreshWorker,
}: {
  upload: UploadState;
  workerOnline: boolean;
  onCancel: (force?: boolean) => void;
  onOpenJob: (id: string) => void;
  onRefreshWorker: () => void;
}) {
  const { phase, progress, fileMeta, stage, jobId, error } = upload;

  if (phase === "uploading") {
    return (
      <div className="upload-status is-uploading">
        <div className="status-top">
          <span className="status-icon">
            <FileUp size={19} />
          </span>
          <div className="status-copy">
            <b>Mengunggah “{fileMeta?.name}”</b>
            <span>{fileMeta?.sizeMb} MB · jangan tutup tab ini</span>
          </div>
          <span className="status-percent">{Math.round(progress)}%</span>
        </div>
        <div className="status-bar">
          <i style={{ width: `${progress}%` }} />
        </div>
        <div className="status-foot">
          <span>Berkas dipindai dulu sebelum masuk antrean.</span>
          <button className="link-btn" onClick={() => onCancel()}>
            <X size={12} /> Batalkan
          </button>
        </div>
      </div>
    );
  }

  if (phase === "queued") {
    return (
      <div className="upload-status is-queued">
        <div className="status-top">
          <span className="status-icon">
            <Timer size={19} />
          </span>
          <div className="status-copy">
            <b>Menunggu antrean</b>
            <span>
              {fileMeta?.name} · {fileMeta?.sizeMb} MB
            </span>
          </div>
          <span className="queue-pill">#1</span>
        </div>
        <div className="queue-grid">
          <div>
            <span>Posisi antrean</span>
            <b>1</b>
          </div>
          <div>
            <span>Perkiraan mulai</span>
            <b>±3 menit</b>
          </div>
          <div>
            <span>Pelabelan</span>
            <b>
              {fileMeta?.diarized
                ? `Aktif · ${fileMeta.speakers} pembicara · 2× kuota`
                : "Mati"}
            </b>
          </div>
        </div>
        {!workerOnline ? (
          <div className="offline-note">
            <WifiOff size={16} />
            <p>
              <b>Pekerja transkripsi sedang offline.</b> Job tetap aman di antrean dan akan mulai
              otomatis saat pekerja tersedia.
            </p>
            <button className="btn btn-ghost btn-sm" onClick={onRefreshWorker}>
              Periksa pekerja
            </button>
          </div>
        ) : null}
        <div className="status-foot">
          <span>Audio disimpan sementara maksimal 24 jam.</span>
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
          <span>Kamu boleh menutup tab ini. Job berjalan di server.</span>
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
            <b>Transkrip siap</b>
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
            Buka transkrip <ArrowRight size={14} />
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => onCancel(true)}>
            <RotateCcw size={14} /> Unggah berkas lain
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
            <b>Unggahan gagal</b>
            <span>{error ?? "Berkas tidak bisa diproses."}</span>
          </div>
        </div>
        <div className="done-actions">
          <button className="btn btn-ghost btn-sm" onClick={() => onCancel(true)}>
            <RotateCcw size={14} /> Coba lagi
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
  workerOnline,
  onRefreshWorker,
  onPickFile,
  onCancelUpload,
  onOpenJob,
  onOpenConsent,
  onToast,
}: {
  upload: UploadState;
  quota: QuotaView;
  workerOnline: boolean;
  onRefreshWorker: () => void;
  onPickFile: (file: File, meta: UploadFileMeta) => void;
  onCancelUpload: (force?: boolean) => void;
  onOpenJob: (id: string) => void;
  onOpenConsent: () => void;
  onToast: (message: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [language, setLanguage] = useState<UploadFileMeta["language"]>("id");
  const [diarized, setDiarized] = useState(false);
  const [speakerCount, setSpeakerCount] = useState(2);
  const [privacyAgreed, setPrivacyAgreed] = useState(false);

  const busy = ["uploading", "queued", "processing"].includes(upload.phase);

  const requireConsent = () => {
    if (privacyAgreed) return true;
    onToast("Centang persetujuan Pemberitahuan Privasi v1.2 sebelum mengunggah.");
    return false;
  };

  const handleFile = (file: File | undefined) => {
    if (!file || !requireConsent()) return;
    const ext = file.name.split(".").pop()?.toUpperCase() ?? "";
    if (!FORMATS.includes(ext)) {
      onToast(`Format .${ext.toLowerCase()} belum didukung. Pakai ${FORMATS.join(", ")}.`);
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      onToast(`Berkas ${Math.round(file.size / 1024 / 1024)} MB melebihi batas 200 MB.`);
      return;
    }
    onPickFile(file, {
      name: file.name,
      sizeMb: Math.round((file.size / 1024 / 1024) * 10) / 10,
      diarized,
      speakers: diarized ? speakerCount : 1,
      language,
    });
  };

  const used = quota.used;
  const total = quota.minutes;
  const percent = Math.min(100, Math.round((used / total) * 100));

  return (
    <section className="panel upload-panel">
      <div className="upload-glow" />
      <div className="upload-head">
        <div className="upload-title">
          <span className="upload-icon">
            <FolderUp size={16} />
          </span>
          <div>
            <b>Unggah berkas audio</b>
            <span>{FORMATS.join(" · ")}</span>
          </div>
        </div>
        <button
          className={`worker-chip ${workerOnline ? "is-online" : "is-offline"}`}
          onClick={onRefreshWorker}
          title="Klik untuk memeriksa status pekerja"
        >
          <i /> {workerOnline ? "Pekerja online" : "Pekerja offline"}
        </button>
      </div>

      {upload.phase !== "idle" ? (
        <StatusCard
          upload={upload}
          workerOnline={workerOnline}
          onCancel={onCancelUpload}
          onOpenJob={onOpenJob}
          onRefreshWorker={onRefreshWorker}
        />
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
            handleFile(e.dataTransfer.files?.[0]);
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
          <b>Tarik berkas ke sini</b>
          <p>
            atau pilih dari perangkat. Maksimal <strong>200 MB</strong> dan <strong>90 menit</strong>{" "}
            per berkas.
          </p>
          <div className="drop-actions">
            <button
              className="btn btn-primary"
              onClick={() => {
                if (requireConsent()) inputRef.current?.click();
              }}
            >
              <FileUp size={15} /> Pilih berkas
            </button>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            hidden
            onChange={(e) => {
              handleFile(e.target.files?.[0]);
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
            <p>Default mati · maks 8 pembicara · 2× kuota</p>
          </div>
          <button
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
          Reset {quota.reset} · {quota.active}/{quota.maxActive} job berjalan
          {diarized ? " · diarisasi memakai 2× kuota" : ""}
        </p>
      </div>

      <label className={`consent-check upload-consent ${privacyAgreed ? "is-checked" : ""}`}>
        <input
          type="checkbox"
          checked={privacyAgreed}
          onChange={(e) => setPrivacyAgreed(e.target.checked)}
          disabled={busy}
        />
        <span className="check-box">{privacyAgreed ? "✓" : ""}</span>
        <span>
          Saya menyetujui <b>Pemberitahuan Privasi v1.2</b> dan menyatakan berusia minimal 18
          tahun.
        </span>
      </label>

      <button className="consent-note" onClick={onOpenConsent}>
        <ShieldCheck size={15} />
        <span>
          Pemberitahuan privasi v1.2 — audio dihapus ≤24 jam, transkrip disimpan 30 hari.
        </span>
        <ChevronRight size={14} />
      </button>
    </section>
  );
}
