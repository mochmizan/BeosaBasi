import { Link } from "react-router-dom";
import { Compass } from "lucide-react";

export default function NotFoundPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">404</div>
          <h1>
            Halaman <em>tidak ditemukan.</em>
          </h1>
          <p className="page-sub">Tautan mungkin sudah berubah atau job sudah dihapus.</p>
        </div>
      </div>
      <div className="empty-library">
        <div className="empty-icon">
          <Compass size={22} />
        </div>
        <h3>Kembali ke studio</h3>
        <p>Unggah rekaman baru atau buka pustaka job yang tersimpan.</p>
        <Link className="btn btn-primary btn-sm" to="/">
          Buka studio
        </Link>
      </div>
    </div>
  );
}
