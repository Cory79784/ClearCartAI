"use client";

import { useMemo, useState, type MouseEvent } from "react";
import { API_BASE } from "../../lib/api";

export default function LabelingPage() {
  const [labelerId, setLabelerId] = useState("anonymous");
  const [uploaderName, setUploaderName] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState("");
  const [status, setStatus] = useState("Click Load Next Image to begin.");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [packaging, setPackaging] = useState("");
  const [productName, setProductName] = useState("");
  const [busy, setBusy] = useState(false);

  const hasImage = useMemo(() => !!imageSrc && !!sessionId, [imageSrc, sessionId]);

  async function callJson(path: string, body: object) {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || "Request failed");
    return data;
  }

  async function onUpload() {
    if (!uploadFile) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", uploadFile);
      form.append("uploader_name", uploaderName);
      const res = await fetch(`${API_BASE}/labeling/upload`, {
        method: "POST",
        credentials: "include",
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Upload failed");
      setUploadStatus(data.status);
    } catch (e) {
      setUploadStatus(`❌ ${String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function onLoadNext() {
    setBusy(true);
    try {
      const data = await callJson("/labeling/load-next", {
        labeler_id: labelerId || "anonymous",
        session_id: sessionId,
      });
      setSessionId(data.session_id || null);
      setImageSrc(data.image || null);
      setStatus(data.status || "");
      setPackaging("");
      setProductName("");
    } catch (e) {
      setStatus(`❌ ${String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function onImageClick(evt: MouseEvent<HTMLImageElement>) {
    if (!sessionId || !imageSrc || busy) return;
    const img = evt.currentTarget;
    const rect = img.getBoundingClientRect();

    const localX = evt.clientX - rect.left;
    const localY = evt.clientY - rect.top;

    // Map click from rendered size to original pixel coordinates.
    const scaleX = img.naturalWidth / rect.width;
    const scaleY = img.naturalHeight / rect.height;
    const x = Math.max(0, Math.floor(localX * scaleX));
    const y = Math.max(0, Math.floor(localY * scaleY));
    setBusy(true);
    try {
      const data = await callJson("/labeling/add-point", { session_id: sessionId, x, y });
      setImageSrc(data.image || imageSrc);
      setStatus(data.status || "");
    } catch (e) {
      setStatus(`❌ ${String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function onReset() {
    if (!sessionId) return;
    setBusy(true);
    try {
      const data = await callJson("/labeling/reset", { session_id: sessionId });
      setImageSrc(data.image || null);
      setStatus(data.status || "");
    } catch (e) {
      setStatus(`❌ ${String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function onSkip() {
    if (!sessionId) return;
    setBusy(true);
    try {
      const data = await callJson("/labeling/skip", {
        session_id: sessionId,
        labeler_id: labelerId || "anonymous",
        reason: "not_clear",
      });
      setImageSrc(data.image || null);
      setStatus(data.status || "");
      setSessionId(data.session_id || sessionId);
    } catch (e) {
      setStatus(`❌ ${String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function onSaveNext() {
    if (!sessionId) return;
    setBusy(true);
    try {
      const data = await callJson("/labeling/save", {
        session_id: sessionId,
        packaging,
        product_name: productName,
      });
      setImageSrc(data.image || null);
      setStatus(data.status || "");
      setSessionId(data.session_id || sessionId);
      setPackaging("");
      setProductName("");
    } catch (e) {
      setStatus(`❌ ${String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="labelWorkspace">
        <aside className="leftStack">
          <section className="card">
            <h3 className="pageTitle">Upload Product Folder</h3>
            <p className="muted">Upload a ZIP file containing one product folder with images.</p>
            <input className="input" type="file" accept=".zip" onChange={(e) => setUploadFile(e.target.files?.[0] || null)} />
            <div style={{ height: 10 }} />
            <input className="input" placeholder="Your name (optional)" value={uploaderName} onChange={(e) => setUploaderName(e.target.value)} />
            <div style={{ height: 10 }} />
            <button className="button" style={{ width: "100%" }} disabled={busy || !uploadFile} onClick={onUpload}>Upload & Ingest</button>
          </section>

          <section className="card">
            <h3 className="pageTitle">Labeler Settings</h3>
            <label className="muted">Labeler ID</label>
            <input className="input" value={labelerId} onChange={(e) => setLabelerId(e.target.value)} />
            <div style={{ height: 10 }} />
            <button className="button" style={{ width: "100%" }} disabled={busy} onClick={onLoadNext}>Load Next Image</button>
          </section>
        </aside>

        <section className="card imgCard">
          <h3 className="pageTitle" style={{ textAlign: "center" }}>Click on product to segment</h3>
          <div className="iframeWrap imgViewport" style={{ padding: 8 }}>
            {imageSrc ? (
              <img
                src={imageSrc}
                alt="label target"
                style={{ width: "100%", maxHeight: 640, objectFit: "contain", cursor: "crosshair" }}
                onClick={onImageClick}
              />
            ) : (
              <p className="muted">No image loaded.</p>
            )}
          </div>
          <div className="actionRow">
            <button className="button secondary" disabled={busy || !hasImage} onClick={onReset}>Reset Image</button>
            <button className="button" disabled={busy || !hasImage} onClick={onSkip}>Skip (Not clear) → Next</button>
          </div>
        </section>

        <aside className="card">
          <h3 className="pageTitle">Label Information</h3>
          <label className="muted">Packaging Type</label>
          <input className="input" placeholder="e.g., box, bottle, bag" value={packaging} onChange={(e) => setPackaging(e.target.value)} />
          <div style={{ height: 10 }} />
          <label className="muted">Product Name</label>
          <input className="input" placeholder="e.g., Milk 1L" value={productName} onChange={(e) => setProductName(e.target.value)} />
          <div style={{ height: 12 }} />
          <button className="button" style={{ width: "100%" }} disabled={busy || !hasImage} onClick={onSaveNext}>Save & Load Next</button>
          <div style={{ height: 16 }} />
          <h4 style={{ marginTop: 0 }}>Instructions</h4>
          <ol className="muted" style={{ paddingLeft: 18 }}>
            <li>Click Load Next Image</li>
            <li>Click on the product to segment</li>
            <li>Fill packaging and product name</li>
            <li>Click Save &amp; Load Next</li>
          </ol>
        </aside>
      </div>

      {uploadStatus ? <section className="card"><pre>{uploadStatus}</pre></section> : null}
      <section className="card"><pre>{status}</pre></section>
    </div>
  );
}
