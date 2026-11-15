import { useState } from "react";
import {
  Check,
  Cpu,
  Download,
  Globe2,
  Info,
  Lock,
  Moon,
  ShieldCheck,
  ShieldOff,
  Sparkles,
  Sun,
  Trash2,
  User,
  Users,
  Zap,
} from "lucide-react";
import { api } from "../api/client";
import { pesanGalat } from "../api/errors";
import { useStudio } from "../components/studio";

function Toggle({
  on,
  onChange,
  title,
  desc,
  icon: Icon,
}: {
  on: boolean;
  onChange: (value: boolean) => void;
  title: string;
  desc?: string;
  icon?: typeof Users;
}) {
  return (
    <div className="toggle-row">
      <div className="toggle-copy">
        {Icon ? (
          <span className="toggle-icon">
            <Icon size={15} />
          </span>
        ) : null}
        <div>
          <b>{title}</b>
          {desc ? <p>{desc}</p> : null}
        </div>
      </div>
      <button
        className={`switch ${on ? "is-on" : ""}`}
        onClick={() => onChange(!on)}
        role="switch"
        aria-checked={on}
        aria-label={title}
      >
        <i />
      </button>
    </div>
  );
}

const formats = ["TXT", "SRT", "VTT", "DOCX"];

export default function SettingsPage() {
  const {
    theme,
    toggleTheme,
    toast,
    profile,
    quota,
    consentGiven,
    consent,
    openNotice,
    openGrant,
    onWithdrawConsent,
    navigate,
    workerOnline,
    refreshHealth,
    refreshData,
  } = useStudio();

  const [diarize, setDiarize] = useState(false);
  const [format, setFormat] = useState("TXT");
  const [lang, setLang] = useState("id");
  const [speakerLabels, setSpeakerLabels] = useState(true);

  const used = quota.used;
  const total = quota.minutes;
  const percent = Math.min(100, Math.round((used / total) * 100));

  const deleteAll = () => {
    if (!window.confirm("Hapus semua data akun? Tindakan ini tidak bisa dibatalkan.")) return;
    void (async () => {
      try {
        await api.deleteMe();
        refreshData();
        toast("Semua data akun dijadwalkan terhapus");
      } catch (e) {
        toast(pesanGalat(e));
      }
    })();
  };

  return (
    <div className="page settings-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Pengaturan</div>
          <h1>
            Atur sesuai <em>cara kamu.</em>
          </h1>
          <p className="page-sub">Preferensi transkripsi, privasi, dan retensi untuk akun ini.</p>
        </div>
        <button className="btn btn-primary" onClick={() => toast("Pengaturan berhasil disimpan")}>
          <Check size={16} /> Simpan perubahan
        </button>
      </div>

      <div className="settings-grid">
        <div className="settings-col">
          <section className="panel settings-card">
            <div className="settings-head">
              <span className="settings-icon">
                <User size={17} />
              </span>
              <div>
                <h3>Profil</h3>
                <p>Informasi yang tampil di ruang kerja kamu.</p>
              </div>
              <span className="pill-soft">{profile.pilot}</span>
            </div>

            <div className="profile-row">
              <span className="avatar avatar-xl">{profile.initials}</span>
              <div>
                <b>Foto profil</b>
                <p>Pilot tertutup · maksimal 50 pengguna</p>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => toast("Pemilih foto belum tersedia")}
                >
                  Ganti foto
                </button>
              </div>
            </div>

            <div className="field-grid">
              <label className="field">
                <span>Nama lengkap</span>
                <input key={`name-${profile.email}`} defaultValue={profile.name} />
              </label>
              <label className="field">
                <span>Email</span>
                <input key={`email-${profile.email}`} defaultValue={profile.email} readOnly />
              </label>
            </div>

            <label className="field">
              <span>Bahasa antarmuka</span>
              <div className="select-wrap">
                <Globe2 size={15} />
                <select defaultValue="id">
                  <option value="id">Bahasa Indonesia</option>
                  <option value="en">English</option>
                </select>
              </div>
            </label>

            <div className="pilot-note">
              <Lock size={13} />
              <span>
                Akses lewat undangan dan allowlist email. Pilot ditutup untuk maksimal 50 pengguna.
              </span>
            </div>
          </section>

          <section className="panel settings-card">
            <div className="settings-head">
              <span className="settings-icon">
                <Zap size={17} />
              </span>
              <div>
                <h3>Kuota & batas</h3>
                <p>Berlaku per pengguna, tanpa paket berbayar.</p>
              </div>
              <span className="pill-soft">{percent}% terpakai</span>
            </div>

            <div className="quota-row is-large">
              <span>
                <Zap size={13} /> Kuota hari ini
              </span>
              <b>
                {used} / {total} menit
              </b>
            </div>
            <div className="quota-bar is-large">
              <i style={{ width: `${percent}%` }} />
            </div>
            <p className="settings-quota-note">
              Reset {quota.reset} · {quota.maxActive} job bisa berjalan bersamaan. Diarisasi memakai
              2× kuota.
            </p>

            <div className="limit-grid">
              <div>
                <span>Job berjalan</span>
                <b>
                  {quota.active}/{quota.maxActive}
                </b>
              </div>
              <div>
                <span>Sisa kuota</span>
                <b>{total - used} menit</b>
              </div>
              <div>
                <span>Batas berkas</span>
                <b>200 MB</b>
              </div>
              <div>
                <span>Durasi maks</span>
                <b>90 menit</b>
              </div>
            </div>

            <button className="btn btn-ghost btn-sm" onClick={() => navigate("insights")}>
              Lihat pemakaian
            </button>
          </section>

          <section className="panel settings-card">
            <div className="settings-head">
              <span className="settings-icon">
                <Cpu size={17} />
              </span>
              <div>
                <h3>Transkripsi</h3>
                <p>Model dan fitur yang dipakai saat memproses.</p>
              </div>
            </div>

            <div className="model-locked">
              <span className="model-locked-icon">
                <Sparkles size={16} />
              </span>
              <div>
                <b>whisper-large-v3-turbo</b>
                <p>Self-hosted · dikelola admin · tidak bisa diubah pengguna.</p>
              </div>
              <span className="pill-soft">aktif</span>
            </div>

            <label className="field">
              <span>Bahasa transkripsi default</span>
              <div className="select-wrap">
                <Globe2 size={15} />
                <select value={lang} onChange={(e) => setLang(e.target.value)}>
                  <option value="id">Bahasa Indonesia</option>
                  <option value="en">English</option>
                  <option value="auto">Deteksi otomatis</option>
                </select>
              </div>
            </label>

            <div className="toggle-stack">
              <Toggle
                on={diarize}
                onChange={setDiarize}
                title="Pelabelan pembicara (default)"
                desc="Mati secara default · maksimal 8 pembicara · memakai 2× kuota."
                icon={Users}
              />
              <Toggle
                on={speakerLabels}
                onChange={setSpeakerLabels}
                title="Sertakan label di ekspor"
                desc="Tulis nama pembicara pada TXT, SRT, dan VTT."
                icon={User}
              />
            </div>

            <div className="worker-row">
              <div>
                <b>Status pekerja</b>
                <p>Pemrosesan berjalan di laptop pemilik, bukan di server.</p>
              </div>
              <button
                className={`worker-chip ${workerOnline ? "is-online" : "is-offline"}`}
                onClick={refreshHealth}
              >
                <i /> {workerOnline ? "Online" : "Offline"}
              </button>
            </div>
          </section>
        </div>

        <div className="settings-col">
          <section className="panel settings-card">
            <div className="settings-head">
              <span className="settings-icon">
                <ShieldCheck size={17} />
              </span>
              <div>
                <h3>Privasi & persetujuan</h3>
                <p>Pemberitahuan versi {consent?.version ?? "v1.2"}.</p>
              </div>
              <span className={`pill-soft ${consentGiven ? "is-mint" : "is-coral"}`}>
                {consentGiven ? "aktif" : "belum"}
              </span>
            </div>

            <div className={`consent-card ${consentGiven ? "is-on" : "is-off"}`}>
              <span className="consent-card-icon">
                {consentGiven ? <ShieldCheck size={18} /> : <ShieldOff size={18} />}
              </span>
              <div>
                <b>{consentGiven ? "Persetujuan aktif" : "Persetujuan belum diberikan"}</b>
                <p>
                  {consentGiven
                    ? `Diberikan ${consent?.given ?? "—"}.`
                    : "Unggahan berikutnya akan meminta persetujuan sebelum diproses."}
                </p>
              </div>
            </div>

            <div className="consent-actions">
              <button className="btn btn-ghost btn-sm" onClick={() => openNotice()}>
                Lihat pemberitahuan
              </button>
              {consentGiven ? (
                <button className="btn btn-danger btn-sm" onClick={onWithdrawConsent}>
                  Tarik persetujuan
                </button>
              ) : (
                <button className="btn btn-primary btn-sm" onClick={openGrant}>
                  Beri persetujuan
                </button>
              )}
            </div>

            <div className="retention-mini">
              <div>
                <span>Audio di server</span>
                <b>≤ 24 jam</b>
              </div>
              <div>
                <span>Transkrip</span>
                <b>30 hari</b>
              </div>
              <div>
                <span>Pelatihan model</span>
                <b>Tidak pernah</b>
              </div>
              <div>
                <span>Batas usia</span>
                <b>18+</b>
              </div>
            </div>

            <div className="danger-row">
              <div>
                <b>Hapus semua data</b>
                <p>Semua job, transkrip, dan pengaturan dihapus permanen.</p>
              </div>
              <button className="btn btn-danger btn-sm" onClick={deleteAll}>
                <Trash2 size={14} /> Hapus
              </button>
            </div>
          </section>

          <section className="panel settings-card">
            <div className="settings-head">
              <span className="settings-icon">
                <Download size={17} />
              </span>
              <div>
                <h3>Ekspor & tampilan</h3>
                <p>Format default dan tema aplikasi.</p>
              </div>
            </div>

            <div className="field">
              <span>Format ekspor default</span>
              <div className="format-chips">
                {formats.map((f) => (
                  <button
                    key={f}
                    className={`format-chip ${format === f ? "is-active" : ""}`}
                    onClick={() => setFormat(f)}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>

            <div className="field">
              <span>Tema</span>
              <div className="theme-options">
                <button
                  className={`theme-option ${theme === "dark" ? "is-active" : ""}`}
                  onClick={() => theme !== "dark" && toggleTheme()}
                >
                  <span className="theme-preview dark">
                    <i />
                    <i />
                    <i />
                  </span>
                  <span>
                    <Moon size={14} /> Gelap
                  </span>
                  {theme === "dark" ? <Check size={14} className="theme-check" /> : null}
                </button>
                <button
                  className={`theme-option ${theme === "light" ? "is-active" : ""}`}
                  onClick={() => theme !== "light" && toggleTheme()}
                >
                  <span className="theme-preview light">
                    <i />
                    <i />
                    <i />
                  </span>
                  <span>
                    <Sun size={14} /> Terang
                  </span>
                  {theme === "light" ? <Check size={14} className="theme-check" /> : null}
                </button>
              </div>
            </div>

            <div className="privacy-line">
              <ShieldCheck size={13} />
              <span>Audio selalu dihapus ≤24 jam. Tidak ada opsi menyimpannya lebih lama.</span>
            </div>
          </section>

          <section className="panel settings-card">
            <div className="settings-head">
              <span className="settings-icon">
                <Info size={17} />
              </span>
              <div>
                <h3>Tentang Beosabasi</h3>
                <p>Pilot tertutup Bahasa Indonesia.</p>
              </div>
              <span className="pill-soft">v0.1.0</span>
            </div>

            <div className="about-rows">
              <div>
                <span>Mesin transkripsi</span>
                <b>whisper-large-v3-turbo</b>
              </div>
              <div>
                <span>Pemrosesan</span>
                <b>Self-hosted</b>
              </div>
              <div>
                <span>Penyimpanan</span>
                <b>Audio 24 jam · teks 30 hari</b>
              </div>
              <div>
                <span>Akses</span>
                <b>Google · undangan · allowlist</b>
              </div>
            </div>

            <p className="about-foot">
              Beosabasi — unggah rekaman, sisanya kami catat. Dibuat untuk pilot tertutup Bahasa
              Indonesia.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
