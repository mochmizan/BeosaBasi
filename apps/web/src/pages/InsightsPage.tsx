import { useMemo, type CSSProperties } from "react";
import {
  ArrowUpRight,
  CalendarDays,
  Clock,
  FileAudio,
  FileText,
  Flame,
  Gauge,
  Loader2,
  ShieldCheck,
  Sparkles,
  Timer,
  TrendingUp,
  Users,
  Zap,
} from "lucide-react";
import { useStudio } from "../components/studio";
import { statusMeta, uiJobCard } from "../lib/adapters";

const weekly = [
  { day: "Sen", minutes: 18 },
  { day: "Sel", minutes: 34 },
  { day: "Rab", minutes: 12 },
  { day: "Kam", minutes: 46 },
  { day: "Jum", minutes: 28 },
  { day: "Sab", minutes: 52 },
  { day: "Min", minutes: 24 },
];

const languages = [
  { name: "Indonesia", value: 86, color: "var(--accent)" },
  { name: "Inggris", value: 9, color: "var(--sky)" },
  { name: "Campur", value: 5, color: "var(--mint)" },
];

const retention = [
  { label: "Audio mentah", note: "Dihapus otomatis setelah job selesai", value: "≤ 24 jam" },
  { label: "Transkrip", note: "Bisa diedit, diekspor, atau dihapus lebih awal", value: "30 hari" },
  { label: "Data pelatihan", note: "Tidak pernah dipakai melatih model", value: "Tidak ada" },
];

const toneVar: Record<string, string> = {
  mint: "var(--mint)",
  amber: "var(--amber)",
  violet: "var(--violet)",
  coral: "var(--accent)",
  slate: "var(--slate)",
};

export default function InsightsPage() {
  const { jobs, quota, navigate } = useStudio();
  const uiJobs = useMemo(() => jobs.map(uiJobCard), [jobs]);

  const max = Math.max(...weekly.map((d) => d.minutes));
  const weekTotal = weekly.reduce((acc, d) => acc + d.minutes, 0);
  const completed = uiJobs.filter((job) => job.status === "completed");
  const active = uiJobs.filter((job) => ["queued", "processing"].includes(job.status)).length;
  const pct = Math.min(100, Math.round((quota.used / quota.minutes) * 100));

  const statusCounts = ["completed", "queued", "processing", "failed", "expired"].map((key) => ({
    key,
    label: statusMeta(key).label,
    tone: statusMeta(key).tone,
    value: uiJobs.filter((job) => job.status === key).length,
  }));
  const maxStatus = Math.max(1, ...statusCounts.map((s) => s.value));

  const stats = [
    {
      label: "Kuota hari ini",
      value: `${quota.used}/${quota.minutes}`,
      suffix: "menit",
      icon: Clock,
      delta: `reset ${quota.reset}`,
      tone: "coral",
    },
    {
      label: "Job selesai",
      value: `${completed.length}`,
      suffix: `dari ${uiJobs.length} job`,
      icon: FileText,
      delta: `${active} masih berjalan`,
      tone: "mint",
    },
    {
      label: "Median xRT",
      value: "9,4×",
      suffix: "lebih cepat dari real-time",
      icon: Gauge,
      delta: "whisper-large-v3-turbo",
      tone: "violet",
    },
    {
      label: "Rasio edit",
      value: "3,2%",
      suffix: "kata disunting",
      icon: Sparkles,
      delta: "dari total kata",
      tone: "amber",
    },
  ];

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Pemakaian</div>
          <h1>
            Kuota dan <em>pemakaian.</em>
          </h1>
          <p className="page-sub">
            Pantau menit yang terpakai, antrean, dan retensi data tujuh hari terakhir.
          </p>
        </div>
        <div className="range-chip">
          <CalendarDays size={14} /> 7 hari terakhir
        </div>
      </div>

      <div className="stat-grid">
        {stats.map(({ label, value, suffix, icon: Icon, delta, tone }) => (
          <div key={label} className={`stat-card tone-${tone}`}>
            <div className="stat-top">
              <span className="stat-icon">
                <Icon size={17} />
              </span>
              <span className="stat-delta">
                <TrendingUp size={12} /> {delta}
              </span>
            </div>
            <b className="stat-value">
              {value}
              <span className="stat-suffix">{suffix}</span>
            </b>
            <span className="stat-label">{label}</span>
          </div>
        ))}
      </div>

      <div className="insight-grid">
        <section className="panel chart-panel">
          <div className="panel-title-row">
            <div>
              <h3>Menit ditranskripsi</h3>
              <p>Rata-rata {Math.round(weekTotal / weekly.length)} menit per hari</p>
            </div>
            <div className="chart-legend">
              <i /> Menit audio
            </div>
          </div>

          <div className="bar-chart">
            {weekly.map((d) => (
              <div key={d.day} className={`bar-col ${d.minutes === max ? "is-peak" : ""}`}>
                <span className="bar-value">{d.minutes}</span>
                <div className="bar-track">
                  <div className="bar" style={{ height: `${(d.minutes / max) * 100}%` }} />
                </div>
                <span className="bar-day">{d.day}</span>
              </div>
            ))}
          </div>

          <div className="chart-foot">
            <span>
              <Flame size={14} /> 5 hari berturut-turut mengunggah
            </span>
            <span className="chart-total">{weekTotal} menit total</span>
          </div>
          <div className="lang-inline">
            {languages.map((l) => (
              <span key={l.name}>
                <i style={{ background: l.color }} /> {l.name} <b>{l.value}%</b>
              </span>
            ))}
          </div>
        </section>

        <section className="panel quota-panel">
          <div className="panel-title-row">
            <div>
              <h3>Kuota harian</h3>
              <p>Reset setiap {quota.reset}</p>
            </div>
            <span className="pill-soft">{pct}% terpakai</span>
          </div>

          <div className="quota-main">
            <div className="quota-ring" style={{ "--p": `${pct * 3.6}deg` } as CSSProperties}>
              <div className="quota-ring-inner">
                <b>{quota.used}</b>
                <span>dari {quota.minutes} menit</span>
              </div>
            </div>
            <div className="quota-side">
              <div>
                <span>Job berjalan</span>
                <b>
                  {quota.active}/{quota.maxActive}
                </b>
              </div>
              <div>
                <span>Sisa kuota</span>
                <b>{quota.minutes - quota.used} menit</b>
              </div>
              <div>
                <span>Antrean</span>
                <b>{statusCounts.find((s) => s.key === "queued")?.value ?? 0} job</b>
              </div>
            </div>
          </div>

          <div className="quota-facts">
            <span>
              <Users size={12} /> Diarisasi memakai 2× kuota
            </span>
            <span>
              <ShieldCheck size={12} /> Audio ≤24 jam · transkrip 30 hari
            </span>
          </div>

          <button className="btn btn-ghost btn-sm quota-cta" onClick={() => navigate("settings")}>
            Kelola kuota & privasi <ArrowUpRight size={13} />
          </button>
        </section>
      </div>

      <div className="insight-grid second">
        <section className="panel usage-panel">
          <div className="panel-title-row">
            <div>
              <h3>Status job</h3>
              <p>{uiJobs.length} job di ruang kerja</p>
            </div>
            <Timer size={15} className="panel-glyph" />
          </div>

          <ul className="status-list">
            {statusCounts.map((item) => (
              <li key={item.key}>
                <span className="status-list-head">
                  <span className={`status-dot-mini tone-${item.tone}`} />
                  <span>{item.label}</span>
                  <b>{item.value}</b>
                </span>
                <span className="status-track">
                  <i
                    style={{
                      width: `${(item.value / maxStatus) * 100}%`,
                      background: toneVar[item.tone],
                    }}
                  />
                </span>
              </li>
            ))}
          </ul>

          <div className="status-foot">
            <Zap size={13} /> {active} job menunggu atau sedang diproses
          </div>
        </section>

        <section className="panel retention-panel">
          <div className="panel-title-row">
            <div>
              <h3>Retensi data</h3>
              <p>Otomatis, tanpa perlu tindakan</p>
            </div>
            <span className="pill-soft">
              <ShieldCheck size={11} /> privasi
            </span>
          </div>

          <ul className="retention-list">
            {retention.map((item) => (
              <li key={item.label}>
                <div>
                  <b>{item.label}</b>
                  <p>{item.note}</p>
                </div>
                <span>{item.value}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="panel recent-mini">
          <div className="panel-title-row">
            <div>
              <h3>Job terakhir</h3>
              <p>Empat unggahan terbaru</p>
            </div>
          </div>
          <ul className="mini-list">
            {uiJobs.slice(0, 4).map((job) => {
              const meta = statusMeta(job.status);
              return (
                <li key={job.id}>
                  <span className={`mini-icon tone-${meta.tone}`}>
                    {job.status === "processing" ? <Loader2 size={14} /> : <FileAudio size={14} />}
                  </span>
                  <span className="mini-copy">
                    <b>{job.title}</b>
                    <span>
                      {meta.label} · {job.duration}
                    </span>
                  </span>
                  <span className={`mini-acc tone-${meta.tone}`}>{job.format}</span>
                </li>
              );
            })}
          </ul>
          <div className="recent-foot">
            <span>{uiJobs.length} job tersimpan</span>
            <button className="btn btn-ghost btn-sm" onClick={() => navigate("library")}>
              Buka pustaka <ArrowUpRight size={13} />
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
