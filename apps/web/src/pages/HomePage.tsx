import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import ErrorMessage from "../components/ErrorMessage";

export default function HomePage(): React.JSX.Element {
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let aktif = true;
    api
      .getHealth()
      .then((h) => {
        if (aktif) setStatus(h.status);
      })
      .catch((e: unknown) => {
        if (aktif) setError(e);
      });
    return () => {
      aktif = false;
    };
  }, []);

  return (
    <section>
      <h1>BeosaBasi</h1>
      <p>Unggah audio, terima transkrip Bahasa Indonesia berpenanda waktu.</p>
      {error !== null && <ErrorMessage error={error} />}
      {error === null && (
        <p className="bb-muted">
          Status API: {status === null ? "memeriksa…" : status}
        </p>
      )}
      <p>
        <Link className="bb-button" to="/jobs">
          Lihat pekerjaan
        </Link>
      </p>
    </section>
  );
}
