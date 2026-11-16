import { useState } from "react";
import {
  Check,
  Cpu,
  Download,
  Globe2,
  Info,
  Lock,
  Minus,
  Moon,
  Plus,
  Sparkles,
  Sun,
  Trash2,
  Users,
  Zap,
} from "lucide-react";
import { api } from "../api/client";
import { pesanGalat } from "../api/errors";
import { useStudio, type StudioPrefs } from "../components/studio";

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
        type="button"
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

const EXPORT_FORMATS: { id: StudioPrefs["defaultExportFormat"]; label: string }[] = [
  { id: "txt", label: "TXT" },
  { id: "srt", label: "SRT" },
  { id: "vtt", label: "VTT" },
  { id: "docx", label: "DOCX" },
];

export default function SettingsPage() {
  const {
    theme,
    toggleTheme,
    toast,
    quota,
    prefs,
    updatePrefs,
    navigate,
    workerOnline,
    refreshHealth,
    refreshData,
    jobs,
  } = useStudio();

  const [confirmClearSession, setConfirmClearSession] = useState(false);

  const used = quota.used;
  const total = quota.minutes;
  const percent = Math.min(100, Math.round((used / total) * 100));

  const clearSessionData = () => {
    void (async () => {
      try {
        await api.deleteMe();
        setConfirmClearSession(false);
        refreshData();
        toast("Seluruh riwayat job dan sesi peramban ini telah dihapus");
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
          <p className="page-sub">
            Preferensi default untuk perekam suara, unggahan, ekspor transkrip, tema, dan manajemen
            sesi peramban. Semua tersimpan otomatis.
          </p>
        </div>
      </div>

      <div className="settings-grid">
        <div className="settings-col">
          <section className="panel settings-card">
            <div className="settings-head">
              <span className="settings-icon">
                <Cpu size={17} />
              </span>
              <div>
                <h3>Preferensi Transkripsi</h3>
                <p>Pengaturan awal saat merekam suara atau mengunggah berkas baru.</p>
              </div>
              <span className="pill-soft is-mint">tersimpan otomatis</span>
            </div>

            <div className="model-locked">
              <span className="model-locked-icon">
                <Sparkles size={16} />
              </span>
              <div>
                <b>whisper-large-v3-turbo</b>
                <p>Inferensi GPU mandiri (int8_float16) · dioptimalkan untuk Bahasa Indonesia.</p>
              </div>
              <span className="pill-soft">aktif</span>
            </div>

            <label className="field">
              <span>Bahasa audio default</span>
              <div className="select-wrap">
                <Globe2 size={15} />
                <select
                  value={prefs.defaultLanguage}
                  onChange={(e) => {
                    updatePrefs({
                      defaultLanguage: e.target.value as StudioPrefs["defaultLanguage"],
                    });
                    toast("Bahasa default diperbarui");
                  }}
                >
                  <option value="id">Bahasa Indonesia</option>
                  <option value="en">English</option>
                  <option value="auto">Deteksi otomatis</option>
                </select>
              </div>
            </label>

            <div className="toggle-stack">
              <Toggle
                on={prefs.defaultDiarization}
                onChange={(val) => {
                  updatePrefs({ defaultDiarization: val });
                  toast(
                    val
                      ? "Pelabelan pembicara diaktifkan secara default"
                      : "Pelabelan pembicara dimatikan secara default",
                  );
                }}
                title="Pelabelan pembicara (default)"
                desc="Pisahkan pembicara otomatis · maksimal 8 orang · memakai 2× kuota."
                icon={Users}
              />
            </div>

            {prefs.defaultDiarization ? (
              <div className="speaker-estimate">
                <div className="speaker-estimate-copy">
                  <label htmlFor="settings-speaker-count">Jumlah pembicara default</label>
                  <span>Petunjuk awal jumlah pembicara (2–8 orang)</span>
                </div>
                <div className="speaker-stepper">
                  <button
                    type="button"
                    onClick={() =>
                      updatePrefs({
                        defaultSpeakers: Math.max(2, prefs.defaultSpeakers - 1),
                      })
                    }
                    disabled={prefs.defaultSpeakers <= 2}
                    aria-label="Kurangi jumlah pembicara default"
                  >
                    <Minus size={13} />
                  </button>
                  <input
                    id="settings-speaker-count"
                    type="number"
                    min="2"
                    max="8"
                    value={prefs.defaultSpeakers}
                    onChange={(e) =>
                      updatePrefs({
                        defaultSpeakers: Math.min(8, Math.max(2, Number(e.target.value) || 2)),
                      })
                    }
                  />
                  <button
                    type="button"
                    onClick={() =>
                      updatePrefs({
                        defaultSpeakers: Math.min(8, prefs.defaultSpeakers + 1),
                      })
                    }
                    disabled={prefs.defaultSpeakers >= 8}
                    aria-label="Tambah jumlah pembicara default"
                  >
                    <Plus size={13} />
                  </button>
                </div>
              </div>
            ) : null}

            <div className="worker-row">
              <div>
                <b>Status perangkat pekerja</b>
                <p>Pemrosesan berjalan di perangkat GPU pekerja yang terhubung keluar ke server.</p>
              </div>
              <button
                type="button"
                className={`worker-chip ${workerOnline ? "is-online" : "is-offline"}`}
                onClick={() => {
                  refreshHealth();
                  toast("Memeriksa status pekerja…");
                }}
              >
                <i /> {workerOnline ? "Online" : "Tertunda"}
              </button>
            </div>
          </section>

          <section className="panel settings-card">
            <div className="settings-head">
              <span className="settings-icon">
                <Zap size={17} />
              </span>
              <div>
                <h3>Kuota & Batas Layanan</h3>
                <p>Berlaku per jaringan harian (WIB), gratis tanpa akun.</p>
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
              Reset setiap pukul {quota.reset} · maksimal {quota.maxActive} job berjalan bersamaan.
              Diarisasi memakai 2× kuota.
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
                <b>{Math.max(0, Math.round((total - used) * 10) / 10)} menit</b>
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
              Lihat rincian pemakaian
            </button>
          </section>
        </div>

        <div className="settings-col">
          <section className="panel settings-card">
            <div className="settings-head">
              <span className="settings-icon">
                <Download size={17} />
              </span>
              <div>
                <h3>Ekspor & Tampilan</h3>
                <p>Format unduhan dan tema warna aplikasi.</p>
              </div>
            </div>

            <div className="field">
              <span>Format ekspor pilihan</span>
              <div className="format-chips">
                {EXPORT_FORMATS.map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    className={`format-chip ${prefs.defaultExportFormat === f.id ? "is-active" : ""}`}
                    onClick={() => {
                      updatePrefs({ defaultExportFormat: f.id });
                      toast(`Format ekspor default diatur ke ${f.label}`);
                    }}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="toggle-stack">
              <Toggle
                on={prefs.includeSpeakerLabels}
                onChange={(val) => {
                  updatePrefs({ includeSpeakerLabels: val });
                  toast(
                    val
                      ? "Label pembicara disertakan saat ekspor"
                      : "Label pembicara disembunyikan pada ekspor TXT/SRT/VTT",
                  );
                }}
                title="Sertakan nama pembicara di ekspor"
                desc="Tampilkan awalan nama pembicara pada hasil unduhan TXT, SRT, dan VTT."
                icon={Users}
              />
            </div>

            <div className="field">
              <span>Tema ruang kerja</span>
              <div className="theme-options">
                <button
                  type="button"
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
                  type="button"
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
          </section>

          <section className="panel settings-card">
            <div className="settings-head">
              <span className="settings-icon">
                <Lock size={17} />
              </span>
              <div>
                <h3>Sesi Peramban & Retensi Data</h3>
                <p>Tanpa registrasi dan tanpa penyimpanan identitas pribadi.</p>
              </div>
              <span className="pill-soft">anonim</span>
            </div>

            <div className="retention-mini">
              <div>
                <span>Audio di server</span>
                <b>Hapus ≤ 24 jam</b>
              </div>
              <div>
                <span>Transkrip teks</span>
                <b>Hapus ≤ 30 hari</b>
              </div>
              <div>
                <span>Job di sesi ini</span>
                <b>{jobs.length} job</b>
              </div>
              <div>
                <span>Identitas</span>
                <b>Token sesi lokal</b>
              </div>
            </div>

            <div className="privacy-line">
              <Lock size={13} />
              <span>
                Job dikaitkan dengan sesi peramban ini saja. Menghapus sesi akan langsung menghapus
                seluruh audio, segmen transkrip, dan riwayat job di server.
              </span>
            </div>

            <div className="danger-row">
              <div>
                <b>Reset sesi & hapus semua riwayat</b>
                <p>Hapus permanen semua job, audio sementara, dan transkrip milik sesi ini.</p>
              </div>
              {!confirmClearSession ? (
                <button
                  type="button"
                  className="btn btn-danger btn-sm"
                  onClick={() => setConfirmClearSession(true)}
                >
                  <Trash2 size={14} /> Hapus semua
                </button>
              ) : (
                <div className="inline-delete-actions">
                  <button type="button" className="btn btn-danger btn-sm" onClick={clearSessionData}>
                    Ya, hapus permanen
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => setConfirmClearSession(false)}
                  >
                    Batal
                  </button>
                </div>
              )}
            </div>
          </section>

          <section className="panel settings-card">
            <div className="settings-head">
              <span className="settings-icon">
                <Info size={17} />
              </span>
              <div>
                <h3>Tentang Beosabasi</h3>
                <p>Layanan transkripsi suara Bahasa Indonesia.</p>
              </div>
              <span className="pill-soft">v0.2.0</span>
            </div>

            <div className="about-rows">
              <div>
                <span>Mesin transkripsi</span>
                <b>Whisper large-v3-turbo</b>
              </div>
              <div>
                <span>Masukan audio</span>
                <b>Rekam mikrofon & unggah berkas</b>
              </div>
              <div>
                <span>Retensi otomatis</span>
                <b>Audio 24 jam · teks 30 hari</b>
              </div>
              <div>
                <span>Model akses</span>
                <b>Anonim · tanpa akun</b>
              </div>
            </div>

            <p className="about-foot">
              Beosabasi — rekam atau unggah suara, sisanya kami catat. Dirancang cepat, bersih, dan
              tanpa akun.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
