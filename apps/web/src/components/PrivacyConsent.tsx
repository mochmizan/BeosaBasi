import { useEffect, useState } from "react";
import {
  Clock,
  FileText,
  ShieldCheck,
  ShieldX,
  Sparkles,
  Trash2,
  UserCheck,
  X,
} from "lucide-react";
import type { ConsentView, UploadFileMeta } from "./studio";

export default function PrivacyConsent({
  open,
  pending,
  readOnly = false,
  consent,
  onAgree,
  onClose,
}: {
  open: boolean;
  pending: UploadFileMeta | null;
  readOnly?: boolean;
  consent: ConsentView | null;
  onAgree: () => void;
  onClose: () => void;
}) {
  const [age, setAge] = useState(false);
  const [rights, setRights] = useState(false);

  useEffect(() => {
    if (!open) return;
    setAge(false);
    setRights(false);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const canAgree = age && rights;

  return (
    <div className="consent-overlay" onMouseDown={onClose}>
      <div
        className="consent-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="consent-title"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <button className="consent-close" onClick={onClose} aria-label="Tutup pemberitahuan privasi">
          <X size={17} />
        </button>

        <div className="consent-head">
          <span className="consent-icon">
            <ShieldCheck size={22} />
          </span>
          <div>
            <h2 id="consent-title">
              {readOnly ? "Pemberitahuan privasi" : "Sebelum mengunggah"}
            </h2>
            <p>Beosabasi memproses audio di server milik sendiri, bukan di perangkat kamu.</p>
          </div>
          <span className="consent-version">v1.2 · 2 Nov 2026</span>
        </div>

        {pending && !readOnly ? (
          <div className="consent-file">
            <FileText size={15} />
            <span>{pending.name}</span>
            <b>{pending.sizeMb} MB</b>
            {pending.diarized ? (
              <span className="consent-flag">
                Diarisasi · {pending.speakers} pembicara · 2× kuota
              </span>
            ) : null}
          </div>
        ) : null}

        <ul className="consent-points">
          <li>
            <span className="point-icon is-coral">
              <Clock size={15} />
            </span>
            <div>
              <b>Audio disimpan maksimal 24 jam</b>
              <p>Setelah job selesai, gagal, atau kedaluwarsa, berkas audio dihapus otomatis.</p>
            </div>
          </li>
          <li>
            <span className="point-icon is-violet">
              <FileText size={15} />
            </span>
            <div>
              <b>Transkrip tersimpan 30 hari</b>
              <p>Kamu bisa mengedit, mengekspor, atau menghapusnya lebih awal kapan saja.</p>
            </div>
          </li>
          <li>
            <span className="point-icon is-mint">
              <ShieldX size={15} />
            </span>
            <div>
              <b>Tidak dipakai melatih model</b>
              <p>Audio dan transkrip tidak pernah menjadi data pelatihan model apa pun.</p>
            </div>
          </li>
          <li>
            <span className="point-icon is-amber">
              <UserCheck size={15} />
            </span>
            <div>
              <b>Kamu berusia 18 tahun atau lebih</b>
              <p>Dan punya hak untuk mengunggah rekaman yang memuat suara orang lain.</p>
            </div>
          </li>
        </ul>

        {readOnly ? (
          <div className="consent-status">
            <Sparkles size={14} />
            <span>
              Persetujuan {consent?.version ?? "v1.2"} diberikan pada{" "}
              {consent?.given ?? "belum tercatat"}
            </span>
          </div>
        ) : (
          <div className="consent-checks">
            <label className={`consent-check ${age ? "is-checked" : ""}`}>
              <input type="checkbox" checked={age} onChange={(e) => setAge(e.target.checked)} />
              <span className="check-box">{age ? "✓" : ""}</span>
              <span>
                Saya berusia <b>18 tahun atau lebih</b>.
              </span>
            </label>
            <label className={`consent-check ${rights ? "is-checked" : ""}`}>
              <input type="checkbox" checked={rights} onChange={(e) => setRights(e.target.checked)} />
              <span className="check-box">{rights ? "✓" : ""}</span>
              <span>
                Saya punya hak atas rekaman ini dan menyetujui pemrosesan otomatisnya.
              </span>
            </label>
          </div>
        )}

        <div className="consent-foot">
          <p>
            <Trash2 size={12} /> Persetujuan bisa ditarik dari Pengaturan → Privasi.
          </p>
          <div className="consent-btns">
            <button className="btn btn-ghost" onClick={onClose}>
              {readOnly ? "Tutup" : "Batal"}
            </button>
            {readOnly ? null : (
              <button className="btn btn-primary" disabled={!canAgree} onClick={onAgree}>
                <ShieldCheck size={15} /> {pending ? "Setuju & unggah" : "Setuju"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
