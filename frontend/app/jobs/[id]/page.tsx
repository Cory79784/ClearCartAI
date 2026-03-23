"use client";

import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

export default function JobDetailPage({ params }: { params: { id: string } }) {
  const [job, setJob] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = () =>
      api(`/jobs/${params.id}`)
        .then(setJob)
        .catch((e) => setError(String(e)));
    load();
    const t = setInterval(() => {
      load();
    }, 2500);
    return () => clearInterval(t);
  }, [params.id]);

  return (
    <section className="card">
      <h3 style={{ marginTop: 0 }}>Job {params.id}</h3>
      {job?.status ? <span className={`badge status-${job.status}`}>{job.status}</span> : null}
      {error ? <p className="status-failed">{error}</p> : null}
      <p className="muted">Auto-refreshing every 2.5 seconds.</p>
      <pre>{JSON.stringify(job, null, 2)}</pre>
    </section>
  );
}
