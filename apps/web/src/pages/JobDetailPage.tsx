import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import type { JobDetail, Transcript } from "../api-types";
import { api } from "../api/client";
import ErrorMessage from "../components/ErrorMessage";

export default function JobDetailPage(): React.JSX.Element {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!id) return;
    let aktif = true;
    async function muat(): Promise<void> {
      try {
        const d = await api.getJob(id as string);
        if (!aktif) return;
        setDetail(d);
        if (d.job.state === "completed") {
          setTranscript(await api.getTranscript(id as string));
        }
      } catch (e: unknown) {
        if (aktif) setError(e);
      }
    }
    void muat();
    return () => {
      aktif = false;
    };
  }, [id]);

  if (!id) return <ErrorMessage error={new Error("ID pekerjaan hilang.")} />;
  if (error !== null) return <ErrorMessage error={error} />;
  if (!detail) return <p className="bb-muted">Memuat status pekerjaan…</p>;

  return (
    <section>
      <h1>{detail.job.filename}</h1>
      <div className="bb-card">
        <p>
          Status: <strong>{detail.job.state}</strong>
          {detail.job.stage ? ` (${detail.job.stage})` : ""}
        </p>
        {detail.queue_position !== null && detail.queue_position !== undefined && (
          <p>Antrean ke-{detail.queue_position}</p>
        )}
        {!detail.worker_active && detail.job.state !== "completed" && (
          <p className="bb-muted">
            Pemrosesan tertunda karena perangkat mati. Job aman dan jalan otomatis
            saat perangkat aktif.
          </p>
        )}
      </div>
      {transcript && (
        <div className="bb-card">
          <h2>Transkrip</h2>
          {transcript.segments.map((s) => (
            <p key={s.index}>
              <span className="bb-muted">
                [{s.start.toFixed(1)}–{s.end.toFixed(1)}]
              </span>{" "}
              {s.text}
            </p>
          ))}
        </div>
      )}
    </section>
  );
}
