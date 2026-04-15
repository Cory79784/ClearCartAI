"use client";

import { useEffect, useMemo, useState, type MouseEvent } from "react";
import { API_BASE } from "../../lib/api";

type ProposedLabel = {
  label_id: number;
  image_id: number;
  product_id: number;
  image_relpath: string;
  overlay_b64: string | null;
  similarity_score: number | null;
};

function ProgressBar({ productId }: { productId: number }) {
  const [progress, setProgress] = useState({ done: 0, total: 1 });

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/labeling/progress/${productId}`, {
          credentials: "include",
        });
        if (res.ok) {
          const data = await res.json();
          if (!cancelled) setProgress(data);
        }
      } catch { /* ignore poll errors */ }
    };
    poll();
    const id = setInterval(poll, 2000);
    return () => { cancelled = true; clearInterval(id); };
  }, [productId]);

  const pct = progress.total > 0 ? Math.round((progress.done / progress.total) * 100) : 0;
  const done = pct === 100;

  return (
    <div style={{ margin: "6px 0 10px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: done ? "#15803d" : "#92400e", marginBottom: 4 }}>
        <span>{done ? "✅" : "⏳"} Auto-labeling: {progress.done} / {progress.total}</span>
        <span style={{ fontWeight: 700 }}>{pct}%</span>
      </div>
      <div style={{ background: "#e5e7eb", borderRadius: 4, height: 8, overflow: "hidden" }}>
        <div style={{
          width: `${pct}%`,
          height: "100%",
          background: done ? "#16a34a" : "#f59e0b",
          transition: "width 0.5s ease",
        }} />
      </div>
    </div>
  );
}

export default function LabelingPage() {
  const [labelerId, setLabelerId] = useState("anonymous");
  const [uploaderName, setUploaderName] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadProductName, setUploadProductName] = useState("");
  const [uploadStatus, setUploadStatus] = useState("");
  const [status, setStatus] = useState("Click Load Next Image to begin.");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [packaging, setPackaging] = useState("");
  const [productName, setProductName] = useState("");
  const [busy, setBusy] = useState(false);
  const [currentProductId, setCurrentProductId] = useState<number | null>(null);
  const [proposedBusy, setProposedBusy] = useState(false);
  const [proposedLabels, setProposedLabels] = useState<ProposedLabel[]>([]);
  const [proposedStatus, setProposedStatus] = useState("");
  const [reviewPackaging, setReviewPackaging] = useState("");
  const [reviewProductName, setReviewProductName] = useState("");

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
      form.append("product_name", uploadProductName);
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
      setCurrentProductId(data.product_id ?? null);
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
      setCurrentProductId(data.product_id ?? null);
      setPackaging("");
      setProductName("");
    } catch (e) {
      setStatus(`❌ ${String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function onLoadProposed() {
    setProposedBusy(true);
    try {
      const res = await fetch(`${API_BASE}/labeling/proposed`, { credentials: "include" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setProposedLabels(data.proposed || []);
      setProposedStatus(
        data.proposed?.length
          ? `🟡 ${data.proposed.length} proposed label(s) waiting for review`
          : "✅ No proposed labels"
      );
    } catch (e) {
      setProposedStatus(`❌ ${String(e)}`);
    } finally {
      setProposedBusy(false);
    }
  }

  async function onAccept(labelId: number) {
    setProposedBusy(true);
    try {
      const data = await callJson("/labeling/accept", {
        label_id: labelId,
        packaging: reviewPackaging,
        product_name: reviewProductName,
        labeler_id: labelerId,
      });
      setProposedLabels((prev: ProposedLabel[]) => prev.filter((l: ProposedLabel) => l.label_id !== labelId));
      setProposedStatus(data.status || "✅ Accepted");
    } catch (e) {
      setProposedStatus(`❌ ${String(e)}`);
    } finally {
      setProposedBusy(false);
    }
  }

  async function onReject(imageId: number) {
    setProposedBusy(true);
    try {
      const data = await callJson("/labeling/reject", { image_id: imageId });
      setProposedLabels((prev: ProposedLabel[]) => prev.filter((l: ProposedLabel) => l.image_id !== imageId));
      setProposedStatus(data.status || "🗑️ Rejected");
    } catch (e) {
      setProposedStatus(`❌ ${String(e)}`);
    } finally {
      setProposedBusy(false);
    }
  }

  async function onAcceptAll() {
    const productIds = [...new Set(proposedLabels.map((l: ProposedLabel) => l.product_id))];
    setProposedBusy(true);
    let totalAccepted = 0;
    let totalFailed = 0;
    try {
      for (const pid of productIds) {
        try {
          const data = await callJson("/labeling/accept-all", {
            product_id: pid,
            packaging: reviewPackaging,
            product_name: reviewProductName,
            labeler_id: labelerId,
          });
          totalAccepted += data.accepted || 0;
          totalFailed += data.failed || 0;
        } catch {
          totalFailed++;
        }
      }
      setProposedLabels([]);
      setProposedStatus(
        `✅ Accepted ${totalAccepted} proposed labels` +
        (totalFailed ? ` (${totalFailed} failed — click Load Proposed to recheck)` : "")
      );
    } finally {
      setProposedBusy(false);
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
      setStatus(
        (data.status || "") +
        (data.image ? "\n\n⏳ Auto-annotation running in background — click 🔍 Load Proposed to review results." : "")
      );
      setSessionId(data.session_id || sessionId);
      setCurrentProductId(data.product_id ?? null);
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
            <input
              className="input"
              type="file"
              accept=".zip"
              onChange={(e) => {
                const f = e.target.files?.[0] || null;
                setUploadFile(f);
                if (f) {
                  const nameWithoutExt = f.name.replace(/\.zip$/i, "");
                  setUploadProductName(nameWithoutExt);
                }
              }}
            />
            <div style={{ height: 10 }} />
            <input
              className="input"
              placeholder="Product name (auto-filled from filename)"
              value={uploadProductName}
              onChange={(e) => setUploadProductName(e.target.value)}
            />
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
          {currentProductId !== null && <ProgressBar productId={currentProductId} />}
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

      {/* Proposed Labels Review Section */}
      <section className="card" style={{ marginTop: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
          <h3 className="pageTitle" style={{ margin: 0 }}>
            🟡 Proposed Auto-Annotations
          </h3>
          <button className="button" disabled={proposedBusy} onClick={onLoadProposed} style={{ minWidth: 160 }}>
            🔍 Load Proposed
          </button>
        </div>

        {proposedLabels.length > 0 && (
          <div style={{ marginTop: 12, display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
            <div style={{ flex: 1, minWidth: 140 }}>
              <label className="muted">Packaging (batch)</label>
              <input
                className="input"
                placeholder="e.g., box"
                value={reviewPackaging}
                onChange={(e) => setReviewPackaging(e.target.value)}
              />
            </div>
            <div style={{ flex: 2, minWidth: 180 }}>
              <label className="muted">Product Name (batch)</label>
              <input
                className="input"
                placeholder="e.g., Milk 1L"
                value={reviewProductName}
                onChange={(e) => setReviewProductName(e.target.value)}
              />
            </div>
            <button
              className="button"
              style={{ background: "#16a34a", minWidth: 180 }}
              disabled={proposedBusy}
              onClick={onAcceptAll}
            >
              ✅ Accept All ({proposedLabels.length})
            </button>
          </div>
        )}

        {proposedStatus && (
          <p style={{ marginTop: 8, fontSize: 13, color: proposedLabels.length ? "#b45309" : "#15803d" }}>
            {proposedStatus}
          </p>
        )}

        {proposedLabels.length > 0 && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12, marginTop: 12 }}>
            {proposedLabels.map((lbl) => (
              <div
                key={lbl.label_id}
                style={{
                  border: "2px solid #f59e0b",
                  borderRadius: 8,
                  overflow: "hidden",
                  background: "#fffbeb",
                }}
              >
                {lbl.overlay_b64 ? (
                  <img
                    src={lbl.overlay_b64}
                    alt="proposed overlay"
                    style={{ width: "100%", height: 160, objectFit: "cover", display: "block" }}
                  />
                ) : (
                  <div style={{ height: 160, display: "flex", alignItems: "center", justifyContent: "center", background: "#fef3c7", color: "#92400e", fontSize: 12 }}>
                    No preview
                  </div>
                )}
                <div style={{ padding: "8px 10px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                    <span style={{
                      background: "#f59e0b",
                      color: "#fff",
                      fontSize: 11,
                      fontWeight: 700,
                      padding: "2px 7px",
                      borderRadius: 99,
                    }}>🟡 PROPOSED</span>
                    {lbl.similarity_score != null && (
                      <span style={{ fontSize: 11, color: "#78350f" }}>
                        sim: {(lbl.similarity_score * 100).toFixed(1)}%
                      </span>
                    )}
                  </div>
                  <p style={{ fontSize: 11, color: "#78350f", margin: "2px 0 8px", wordBreak: "break-all" }}>
                    {lbl.image_relpath.split("/").pop()}
                  </p>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button
                      style={{
                        flex: 1, fontSize: 12, padding: "4px 0",
                        background: "#16a34a", color: "#fff",
                        border: "none", borderRadius: 5, cursor: "pointer",
                      }}
                      disabled={proposedBusy}
                      onClick={() => onAccept(lbl.label_id)}
                    >✅ Accept</button>
                    <button
                      style={{
                        flex: 1, fontSize: 12, padding: "4px 0",
                        background: "#dc2626", color: "#fff",
                        border: "none", borderRadius: 5, cursor: "pointer",
                      }}
                      disabled={proposedBusy}
                      onClick={() => onReject(lbl.image_id)}
                    >❌ Reject</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
