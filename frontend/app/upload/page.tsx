"use client";

import { useState } from "react";
import { API_BASE, api } from "../../lib/api";
import { useRouter } from "next/navigation";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  async function onSubmit() {
    if (!file) return;
    setBusy(true);
    setMessage("");
    try {
      const form = new FormData();
      form.append("file", file);
      const upload = await fetch(`${API_BASE}/jobs/upload-zip`, {
        method: "POST",
        credentials: "include",
        body: form,
      }).then((r) => r.json());
      const job = await api("/jobs/submit", {
        method: "POST",
        body: JSON.stringify({ upload_id: upload.upload_id }),
      });
      setMessage(`Job created: ${job.id}`);
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setMessage(`Upload failed: ${String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card" style={{ maxWidth: 760 }}>
      <h3 style={{ marginTop: 0 }}>Upload ZIP for Async Inference</h3>
      <p className="muted">
        Upload a product ZIP. The backend validates it, queues the job, and runs inference with max 2 concurrent jobs.
      </p>
      <input className="input" type="file" accept=".zip" onChange={(e) => setFile(e.target.files?.[0] || null)} />
      <div style={{ height: 12 }} />
      <button className="button" onClick={onSubmit} disabled={!file || busy}>
        {busy ? "Submitting..." : "Upload and Submit"}
      </button>
      {message ? <p className="muted">{message}</p> : null}
    </section>
  );
}
