import { Link, Outlet } from "react-router-dom";

export default function Layout(): React.JSX.Element {
  return (
    <div className="bb-shell">
      <nav className="bb-nav" aria-label="Navigasi utama">
        <div className="bb-nav-inner">
          <Link className="bb-brand" to="/">
            BeosaBasi
          </Link>
          <Link to="/jobs">Pekerjaan</Link>
        </div>
      </nav>
      <main className="bb-main">
        <Outlet />
      </main>
      <footer className="bb-footer">
        Transkripsi Whisper · Diarisasi pyannote community-1 (CC-BY-4.0)
      </footer>
    </div>
  );
}
