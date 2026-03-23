"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../../lib/api";

export default function JobsPage() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = () =>
      api("/jobs")
        .then(setJobs)
        .catch((e) => {
          setJobs([]);
          setError(String(e));
        });
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, []);

  return (
    <section className="card">
      <h3 style={{ marginTop: 0 }}>Jobs</h3>
      {error ? <p className="status-failed">{error}</p> : null}
      {jobs.length === 0 ? <p className="muted">No jobs yet.</p> : null}
      <div className="grid">
        {jobs.map((j) => (
          <article className="card" key={j.id} style={{ marginBottom: 0 }}>
            <div>
              <span className={`status-${j.status}`}>{j.status}</span>
            </div>
            <p className="muted" style={{ marginBottom: 8 }}>
              {j.id}
            </p>
            <Link href={`/jobs/${j.id}`}>View details</Link>
          </article>
        ))}
      </div>
    </section>
  );
}
