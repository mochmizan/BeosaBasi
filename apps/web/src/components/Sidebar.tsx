import {
  ArrowUpRight,
  BarChart3,
  Clock,
  FileUp,
  Home,
  Library,
  Mic,
  Settings,
  X,
} from "lucide-react";
import { modKey } from "../lib/platform";
import { statusMeta, uiJobCard } from "../lib/adapters";
import { useStudio } from "./studio";

export default function Sidebar({
  open,
  onClose,
  onNewUpload,
  onNewRecord,
}: {
  open: boolean;
  onClose: () => void;
  onNewUpload: () => void;
  onNewRecord: () => void;
}) {
  const { view, inputMode, navigate, selectJob, jobs, quota } = useStudio();

  const nav = [
    { id: "home" as const, label: "Studio", icon: Home },
    { id: "library" as const, label: "Pustaka", icon: Library, count: jobs.length },
    { id: "insights" as const, label: "Pemakaian", icon: BarChart3 },
    { id: "settings" as const, label: "Pengaturan", icon: Settings },
  ];

  const used = quota.used;
  const total = quota.minutes;
  const percent = Math.min(100, Math.round((used / total) * 100));
  const recent = jobs.slice(0, 4).map(uiJobCard);

  return (
    <>
      <div className={`sidebar-backdrop ${open ? "is-open" : ""}`} onClick={onClose} />
      <aside className={`sidebar ${open ? "is-open" : ""}`}>
        <div className="brand-row">
          <button className="brand" onClick={() => navigate("home")} aria-label="Beosabasi">
            <span className="brand-mark" aria-hidden="true">
              <svg viewBox="0 0 32 32" focusable="false">
                <path
                  d="M7.8 26.8c-2.9-2.6-4.1-6.6-3.1-10.4C5.8 12 9.6 8.7 14.3 8.2c4.7-.5 9.2 1.8 11.4 5.9 1.3 2.4 1.5 5.4.5 8-1 2.7-3.1 4.8-5.8 5.9-2.9 1.2-6.2.8-8.8-.9Z"
                  fill="#d7262e"
                />
                <path
                  d="M8.4 23.5c.5 2.8 2.1 5.2 4.5 6.6-3.6-.4-6.6-2.8-7.6-6.3-.3-1.1-.5-2.3-.4-3.5.1-.5.7-.6 1-.2.7 1.2 1.6 2.3 2.5 3.4Z"
                  fill="#b81d27"
                />
                <ellipse cx="16.6" cy="15.5" rx="4.6" ry="5.3" fill="#fff5ed" />
                <circle cx="15.7" cy="13.1" r="1.25" fill="#1c222b" />
                <circle cx="15.35" cy="12.75" r="0.4" fill="#fff" />
                <path
                  d="M19.8 11.6c3.6-.6 6.7 1.5 7.4 4.6.7 3.1-1.1 6.3-4.1 7.4-.8.3-1.7.4-2.5.3 1.2-1.3 2-3 2.1-4.8.2-2.2-.7-4.3-2.4-5.8-.5-.4-1.1-.8-1.7-1.1.4-.2.8-.4 1.2-.6Z"
                  fill="#f0d6a8"
                />
                <path
                  d="M27.2 16.2c.4 2.4-.6 4.8-2.6 6.1-.7.5-1.5.8-2.3.9 1.3-1.4 2.1-3.1 2.2-5 0-.6 0-1.2-.1-1.8.9-.4 1.9-.5 2.8-.2Z"
                  fill="#1f2730"
                />
                <path
                  d="M20.2 22.2c1.5 1.3 3.7 1.6 5.6.8-.9 1.4-2.5 2.1-4.1 1.8-.9-.2-1.6-.7-2.1-1.4.2-.4.4-.8.6-1.2Z"
                  fill="#1f2730"
                />
                <circle cx="20.7" cy="12.5" r="0.55" fill="#b98f5f" />
              </svg>
            </span>
            <span className="brand-name">BEOSABASI</span>
          </button>
          <span className="brand-beta">ID · STT</span>
          <button className="icon-btn sidebar-close" onClick={onClose} aria-label="Tutup menu">
            <X size={18} />
          </button>
        </div>

        <div className="side-cta-group">
          <button
            className={`new-rec ${view === "home" && inputMode === "record" ? "is-active-mode" : ""}`}
            onClick={onNewRecord}
          >
            <span className="new-rec-icon">
              <Mic size={16} strokeWidth={2.2} />
            </span>
            Rekam suara
            <kbd>{modKey}⇧R</kbd>
          </button>

          <button
            className={`new-upload-btn ${view === "home" && inputMode === "upload" ? "is-active-mode" : ""}`}
            onClick={onNewUpload}
          >
            <FileUp size={15} strokeWidth={2} />
            <span>Unggah berkas</span>
            <kbd>{modKey}U</kbd>
          </button>
        </div>

        <nav className="nav" aria-label="Navigasi utama">
          {nav.map(({ id, label, icon: Icon, count }) => (
            <button
              key={id}
              className={`nav-item ${view === id ? "is-active" : ""}`}
              onClick={() => navigate(id)}
            >
              <Icon size={18} strokeWidth={1.8} />
              <span>{label}</span>
              {count ? <span className="nav-count">{count}</span> : null}
              {view === id ? <i className="nav-dot" /> : null}
            </button>
          ))}
        </nav>

        <div className="side-section">
          <div className="side-label">
            <span>Terbaru</span>
            <button className="link-btn" onClick={() => navigate("library")}>
              Semua <ArrowUpRight size={13} />
            </button>
          </div>
          {recent.length > 0 ? (
            <ul className="recent-list">
              {recent.map((job) => {
                const meta = statusMeta(job.status);
                return (
                  <li key={job.id}>
                    <button className="recent-item" onClick={() => selectJob(job.id, job.title)}>
                      <span className={`recent-dot tone-${meta.tone}`} />
                      <span className="recent-copy">
                        <span className="recent-title">{job.title}</span>
                        <span className="recent-meta">
                          {meta.label} · {job.duration}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="side-empty-note">Belum ada transkrip di sesi peramban ini.</p>
          )}
        </div>

        <div className="side-bottom">
          <div className="storage-card">
            <div className="storage-top">
              <span className="storage-icon">
                <Clock size={14} />
              </span>
              <span>Kuota harian</span>
              <b>
                {used} / {total} mnt
              </b>
            </div>
            <div className="storage-bar">
              <i style={{ width: `${percent}%` }} />
            </div>
            <p>Reset {quota.reset} · langsung pakai tanpa akun</p>
          </div>
        </div>
      </aside>
    </>
  );
}
