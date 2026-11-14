import { Link } from "react-router-dom";

export default function NotFoundPage(): React.JSX.Element {
  return (
    <section>
      <h1>Halaman tidak ditemukan</h1>
      <p>
        <Link to="/">Kembali ke beranda</Link>
      </p>
    </section>
  );
}
