import { useMemo, type CSSProperties } from "react";
import {
  ArrowUpRight,
  CalendarDays,
  Clock,
  FileAudio,
  FileText,
  Gauge,
  Loader2,
  Lock,
  Sparkles,
  Timer,
  TrendingUp,
  Users,
  Zap,
} from "lucide-react";
import { useStudio } from "../components/studio";
import { statusMeta, uiJobCard } from "../lib/adapters";

const DAY_NAMES = ["Min", "Sen", "Sel", "Rab", "Kam", "Jum", "Sab"];

const retention = [
  { label: "Audio mentah", note: "Dihapus otomatis setelah job selesai/gagal", value: "≤ 24 jam" },
  { label: "Transkrip", note: "Bisa disunting, diekspor, atau dihapus lebih awal", value: "30 hari" },
  { label: "Sesi peramban", note: "Anonim via cookie/token lokal tanpa akun", value: "90 hari" },
  { label: "Data pelatihan", note: "Tidak pernah dipakai melatih model AI", value: "Tidak ada" },
];

const toneVar: Record<string, string> = {
  mint: "var(--mint)",
  amber: "var(--amber)",
  violet: "var(--violet)",
  coral: "var(--accent)",
  slate: "var(--slate)",
};

export default function InsightsPage() {
  const { jobs, quota, navigate, goJob } = useStudio();
  const uiJobs = useMemo(() => jobs.map(uiJobCard), [jobs]);

  // Hitung distribusi 7 hari terakhir dari data job nyata pengguna
  const weekly = useMemo(() => {
    const now = new Date();
    const buckets: { key: string; day: string; minutes: number }[] = [];
    for (let i = 6; i >= 0; i -= 1) {
      const d = new Date(now);
      d.setDate(now.getDate() - i);
      const key = d.toISOString().slice(0, 10);
      buckets.push({
        key,
        day: DAY_NAMES[d.getDay()],
        minutes: 0,
      });
    }
    for (const job of jobs) {
      const dateKey = (job.created_at || "").slice(0, 10);
      const bucket = buckets.find((b) => b.key === dateKey);
      if (bucket) {
        const mins =
          job.billed_minutes && job.billed_minutes > 0
            ? job.billed_minutes
            : (job.duration_seconds ?? 0) / 60;
        bucket.minutes = Math.round((bucket.minutes + mins) * 10) / 10;
      }
    }
    return buckets;
  }, [jobs]);

  const max = Math.max(1, ...weekly.map((d) => d.minutes));
  const weekTotal = Math.round(weekly.reduce((acc, d) => acc + d.minutes, 0) * 10) / 10;
  const completed = uiJobs.filter((job) => job.status === "completed");
  const active = uiJobs.filter((job) => ["queued", "processing"].includes(job.status)).length;
  const diarizedCount = jobs.filter((j) => j.diarization).length;
  const totalAudioMinutes = Math.round(
    completed.reduce((acc, j) => acc + j.seconds / 60, 0) * 10,
  ) / 10;
  const pct = Math.min(100, Math.round((quota.used / quota.minutes) * 100));

  const languages = useMemo(() => {
    const total = Math.max(1, jobs.length);
    const idCount = jobs.filter((j) => j.language === "id").length;
    const enCount = jobs.filter((j) => j.language === "en").length;
    const autoCount = jobs.filter((j) => j.language === "auto").length;
    if (jobs.length === 0) {
      return [
        { name: "Indonesia", value: 100, color: "var(--accent)" },
        { name: "Inggris", value: 0, color: "var(--sky)" },
        { name: "Otomatis", value: 0, color: "var(--mint)" },
      ];
    }
    return [
      { name: "Indonesia", value: Math.round((idCount / total) * 100), color: "var(--accent)" },
      { name: "Inggris", value: Math.round((enCount / total) * 100), color: "var(--sky)" },
      { name: "Otomatis", value: Math.round((autoCount / total) * 100), color: "var(--mint)" },
    ];
  }, [jobs]);

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
      suffix: "menit terpakai",
      icon: Clock,
      delta: `reset ${quota.reset}`,
      tone: "coral",
    },
    {
      label: "Job selesai",
      value: `${completed.length}`,
      suffix: `dari ${uiJobs.length} job`,
      icon: FileText,
      delta: `${active} sedang aktif`,
      tone: "mint",
    },
    {
      label: "Durasi transkrip",
      value: `${totalAudioMinutes}`,
      suffix: "menit audio selesai",
      icon: Gauge,
      delta: "whisper-large-v3-turbo",
      tone: "violet",
    },
    {
      label: "Diarisasi pembicara",
      value: `${diarizedCount}`,
      suffix: "job berlabel pembicara",
      icon: Sparkles,
      delta: "2× kuota saat aktif",
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
            Pantau menit kuota harian (60 menit/hari), status antrean, dan retensi otomatis di sesi
            peramban ini.
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
              <h3>Menit diproses (7 hari terakhir)</h3>
              <p>
                {weekTotal > 0
                  ? `Rata-rata ${Math.round((weekTotal / 7) * 10) / 10} menit per hari`
                  : "Belum ada menit terpakai dalam 7 hari terakhir"}
              </p>
            </div>
            <div className="chart-legend">
              <i /> Menit kuota
            </div>
          </div>

          <div className="bar-chart">
            {weekly.map((d) => (
              <div
                key={d.key}
                className={`bar-col ${d.minutes > 0 && d.minutes === max ? "is-peak" : ""}`}
              >
                <span className="bar-value">{d.minutes}</span>
                <div className="bar-track">
                  <div
                    className="bar"
                    style={{
                      height: `${d.minutes > 0 ? Math.max(8, (d.minutes / max) * 100) : 4}%`,
                    }}
                  />
                </div>
                <span className="bar-day">{d.day}</span>
              </div>
            ))}
          </div>

          <div className="chart-foot">
            <span>
              <Clock size={14} /> Dihitung per tanggal WIB (UTC+7)
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
                <b>{Math.max(0, Math.round((quota.minutes - quota.used) * 10) / 10)} menit</b>
              </div>
              <div>
                <span>Antrean</span>
                <b>{statusCounts.find((s) => s.key === "queued")?.value ?? 0} job</b>
              </div>
            </div>
          </div>

          <div className="quota-facts">
            <span>
              <Users size={12} /> Diarisasi memakai 2× kuota (dikembalikan bila gagal)
            </span>
            <span>
              <Lock size={12} /> Audio ≤24 jam · transkrip 30 hari
            </span>
          </div>

          <button className="btn btn-ghost btn-sm quota-cta" onClick={() => navigate("settings")}>
            Atur preferensi & sesi <ArrowUpRight size={13} />
          </button>
        </section>
      </div>

      <div className="insight-grid second">
        <section className="panel usage-panel">
          <div className="panel-title-row">
            <div>
              <h3>Status job</h3>
              <p>{uiJobs.length} job di sesi ini</p>
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
              <h3>Retensi & privasi teknis</h3>
              <p>Berjalan otomatis di server</p>
            </div>
            <span className="pill-soft">
              <Lock size={11} /> otomatis
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
              <p>Unggahan & rekaman terbaru</p>
            </div>
          </div>
          {uiJobs.length > 0 ? (
            <ul className="mini-list">
              {uiJobs.slice(0, 4).map((job) => {
                const meta = statusMeta(job.status);
                return (
                  <li
                    key={job.id}
                    onClick={() => goJob(job.id)}
                    style={{ cursor: "pointer" }}
                  >
                    <span className={`mini-icon tone-${meta.tone}`}>
                      {job.status === "processing" ? (
                        <Loader2 size={14} className="spin" />
                      ) : (
                        <FileAudio size={14} />
                      )}
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
          ) : (
            <p className="side-empty-note" style={{ marginTop: 12 }}>
              Belum ada job yang tercatat di sesi ini.
            </p>
          )}
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
