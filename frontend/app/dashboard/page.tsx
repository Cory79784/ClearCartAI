"use client";
import Link from "next/link";

export default function DashboardPage() {
  return (
    <div>
      <section className="card">
        <h3 className="pageTitle">Workspace</h3>
        <p className="muted">Use the labeling UI to upload product sets, segment products, skip unclear images, and save labels quickly.</p>
        <div className="subtlePanel">
          <Link href="/labeling">Open Labeling UI</Link>
        </div>
      </section>
      <div className="grid">
        <section className="card">
          <h3 className="pageTitle">Labeling</h3>
          <p className="muted">Primary operator interface for segmentation and metadata entry.</p>
          <Link href="/labeling">Go to Labeling</Link>
        </section>
        <section className="card">
          <h3 className="pageTitle">Administration</h3>
          <p className="muted">Manage users and monitor queue/system status.</p>
          <Link href="/admin">Open Admin</Link>
        </section>
      </div>
    </div>
  );
}
