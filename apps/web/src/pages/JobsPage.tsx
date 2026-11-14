import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { JobSummary } from "../api-types";
import { api } from "../api/client";
import ErrorMessage from "../components/ErrorMessage";

/** Polling 5 detik (detail penuh di TK-043; scaffold polling di TK-040). */
const POLL_MS = 5000;

export default function JobsPage(): React.JSX.Element {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let aktif = true;
    async function muat(): Promise<void> {
      try {
        const res = await api.listJobs();
        if (aktif) {
          setJobs(res.jobs);
          setError(null);
        }
      } catch (e: unknown) {
        if (aktif) setError(e);
      } finally {
        if (aktif) setLoading(false);
      }
    }
    void muat();
    const id = setInterval(() => {
      void muat();
    }, POLL_MS);
    return () => {
      aktif = false;
      clearInterval(id);
    };
  }, []);

  if (loading) return <p className="bb-muted">Memuat daftar pekerjaan…</p>;

  return (
    <section>
      <h1>Pekerjaan</h1>
      {error !== null && <ErrorMessage error={error} />}
      {jobs.length === 0 ? (
        <p className="bb-muted">Belum ada pekerjaan. Unggah menyusul di TK-042.</p>
      ) : (
        <table className="bb-table">
          <thead>
            <tr>
              <th>Berkas</th>
              <th>Status</th>
              <th>Dibuat</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.job_id}>
                <td>
                  <Link to={`/jobs/${j.job_id}`}>{j.filename}</Link>
                </td>
                <td>{j.state}</td>
                <td>{j.created_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
