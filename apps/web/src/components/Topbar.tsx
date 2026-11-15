import {
  ArrowRight,
  Bell,
  ChevronRight,
  Clock,
  FileAudio,
  Menu,
  Moon,
  Search,
  Sun,
} from "lucide-react";
import { modKey } from "../lib/platform";
import { statusMeta } from "../lib/adapters";
import { useStudio } from "./studio";

const labels: Record<string, string> = {
  home: "Studio",
  library: "Pustaka",
  insights: "Pemakaian",
  settings: "Pengaturan",
};

export default function Topbar({
  view,
  workerOnline,
  onPalette,
  onMenu,
}: {
  view: string;
  workerOnline: boolean;
  onPalette: () => void;
  onMenu: () => void;
}) {
  const { query, setQuery, searchResults, selectJob, theme, toggleTheme, profile } = useStudio();

  return (
    <header className="topbar">
      <button className="icon-btn menu-btn" onClick={onMenu} aria-label="Buka menu">
        <Menu size={19} />
      </button>

      <div className="crumb">
        <span>Beosabasi</span>
        <ChevronRight size={13} />
        <b>{labels[view] ?? "Studio"}</b>
      </div>

      <div className="search-wrap">
        <Search size={16} className="search-icon" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") setQuery("");
          }}
          placeholder="Cari transkrip, berkas, pembicara…"
          aria-label="Cari job transkripsi"
        />
        <button className="search-kbd" onClick={onPalette}>
          {modKey}K
        </button>

        {query.trim() !== "" && searchResults.length > 0 ? (
          <div className="search-pop">
            <div className="search-pop-label">Hasil pencarian</div>
            {searchResults.map((job) => {
              const meta = statusMeta(job.status);
              return (
                <button
                  key={job.id}
                  className="search-result"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    selectJob(job.id, job.title);
                    setQuery("");
                  }}
                >
                  <span className={`result-icon tone-${meta.tone}`}>
                    <FileAudio size={15} />
                  </span>
                  <span className="result-copy">
                    <b>{job.title}</b>
                    <span>
                      <Clock size={11} /> {job.duration} · {job.format} · {meta.label}
                    </span>
                  </span>
                  <ArrowRight size={14} className="result-arrow" />
                </button>
              );
            })}
          </div>
        ) : null}
        {query.trim() !== "" && searchResults.length === 0 ? (
          <div className="search-pop is-empty">
            <p>Tidak ada yang cocok dengan “{query}”.</p>
            <span>Coba kata kunci lain atau cek pustaka.</span>
          </div>
        ) : null}
      </div>

      <div className="top-actions">
        <div
          className={`model-chip ${workerOnline ? "" : "is-offline"}`}
          title={workerOnline ? "Pekerja transkripsi online" : "Pekerja transkripsi offline"}
        >
          <span className="model-pulse" />
          large-v3-turbo
        </div>
        <button className="icon-btn" onClick={toggleTheme} aria-label="Ganti tema">
          {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
        </button>
        <button className="icon-btn has-dot" aria-label="Notifikasi">
          <Bell size={17} />
        </button>
        <span className="avatar avatar-sm">{profile.initials}</span>
      </div>
    </header>
  );
}
