import io
import os
import shutil
import tempfile
import threading
import uuid
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ean_system import db, config
from ean_system.sam2_segmenter import SAM2InteractiveSegmenter
from ean_system.image_utils import load_image, apply_mask_overlay
from ean_system.dinov2_embedder import DINOv2Embedder
from ean_system.matcher import InstanceMatcher


RAW_ROOT_DIR = os.getenv("RAW_ROOT_DIR", "/data/raw_products")
OUTPUT_ROOT_DIR = os.getenv("OUTPUT_ROOT_DIR", "/data/labels_output")
LOCK_MINUTES = int(os.getenv("LOCK_MINUTES", "30"))
LABELING_MAX_SIZE = int(os.getenv("LABELING_MAX_SIZE", "1024"))
PRECOMPUTE_ON_LOAD = os.getenv("PRECOMPUTE_ON_LOAD", "1") == "1"
AUTO_ANNOTATE_ENABLED = os.getenv("AUTO_ANNOTATE_ENABLED", "1") == "1"
MAX_AUTO_ANNOTATE_SIBLINGS = int(os.getenv("MAX_AUTO_ANNOTATE_SIBLINGS", "20"))


def _ensure_dirs() -> None:
    Path(OUTPUT_ROOT_DIR).mkdir(parents=True, exist_ok=True)
    Path(RAW_ROOT_DIR).mkdir(parents=True, exist_ok=True)


def _image_to_b64_png(arr: np.ndarray | None) -> str | None:
    if arr is None:
        return None
    img = Image.fromarray(arr.astype(np.uint8))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    import base64

    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


class LabelingService:
    def __init__(self) -> None:
        _ensure_dirs()
        db.init_db()
        self.segmenter: SAM2InteractiveSegmenter | None = None
        self.sessions: dict[str, dict[str, Any]] = {}
        self._segmenter_loaded_image_id: int | None = None
        self._embedder: DINOv2Embedder | None = None
        self._matcher: InstanceMatcher | None = None

    def _get_embedder(self) -> DINOv2Embedder:
        if self._embedder is None:
            self._embedder = DINOv2Embedder()
        return self._embedder

    def _get_matcher(self) -> InstanceMatcher:
        if self._matcher is None:
            self._matcher = InstanceMatcher()
        return self._matcher

    def _get_segmenter(self) -> SAM2InteractiveSegmenter:
        if self.segmenter is None:
            self.segmenter = SAM2InteractiveSegmenter()
        return self.segmenter

    def _warmup_segmenter_async(self, image_id: int, image: np.ndarray) -> None:
        def _run() -> None:
            try:
                segmenter = self._get_segmenter()
                segmenter.set_image(image)
                self._segmenter_loaded_image_id = int(image_id)
            except Exception:
                # Ignore warmup errors; add_point will return explicit error if needed.
                pass

        threading.Thread(target=_run, daemon=True).start()

    def upload_and_ingest(self, zip_path: Path, uploader_name: str, original_filename: str = "", product_name_override: str = "") -> str:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                for member in zip_ref.namelist():
                    member_path = temp_path / member
                    if not str(member_path.resolve()).startswith(str(temp_path.resolve())):
                        return f"❌ Security error: Invalid path in ZIP: {member}"
                zip_ref.extractall(temp_path)

            # Filter out Mac __MACOSX and other hidden/system entries
            extracted_items = [
                p for p in temp_path.iterdir()
                if not p.name.startswith('.') and p.name != '__MACOSX'
            ]
            if len(extracted_items) == 0:
                return "❌ ZIP file is empty"

            if len(extracted_items) == 1 and extracted_items[0].is_dir():
                product_folder = extracted_items[0]
                inferred_name = product_folder.name
            else:
                product_folder = temp_path / "uploaded_product"
                product_folder.mkdir()
                for item in extracted_items:
                    shutil.move(str(item), str(product_folder))
                inferred_name = os.path.splitext(original_filename)[0] if original_filename else "uploaded_product"

            final_name = product_name_override.strip() if product_name_override.strip() else inferred_name
            product_name = product_folder.name
            target_path = Path(RAW_ROOT_DIR) / product_name
            counter = 1
            while target_path.exists():
                target_path = Path(RAW_ROOT_DIR) / f"{product_name}_{counter}"
                counter += 1

            shutil.move(str(product_folder), str(target_path))
            result = db.ingest_product_folder(RAW_ROOT_DIR, target_path.name, name_override=final_name)
            stats = db.get_stats()
            return (
                f"✅ Upload successful!\n\n"
                f"Product: {target_path.name}\n"
                f"Location: {target_path}\n"
                f"Images ingested: {result['images']}\n"
                f"Uploader: {uploader_name or 'Anonymous'}\n\n"
                f"Database stats:\n"
                f"  Total images: {stats['total_images']}\n"
                f"  Unlabeled: {stats['unlabeled_images']}\n"
                f"  Labeled: {stats['labeled_images']}"
            )

    def create_or_get_session(self, session_id: str | None) -> str:
        if session_id and session_id in self.sessions:
            return session_id
        sid = str(uuid.uuid4())
        self.sessions[sid] = {}
        return sid

    def load_next(self, labeler_id: str, session_id: str | None) -> dict[str, Any]:
        sid = self.create_or_get_session(session_id)
        if not labeler_id:
            labeler_id = "anonymous"
        if not db.healthcheck():
            return {"session_id": sid, "image": None, "status": "❌ Database connection failed"}

        result = db.get_next_unlabeled_image(labeler_id, LOCK_MINUTES)
        if result is None:
            stats = db.get_stats()
            return {
                "session_id": sid,
                "image": None,
                "status": (
                    "🎉 No more unlabeled images!\n\n"
                    f"Database stats:\n  Total images: {stats['total_images']}\n"
                    f"  Labeled: {stats['labeled_images']}\n  Unlabeled: {stats['unlabeled_images']}"
                ),
            }

        image_id, image_relpath, product_id = result
        image_path = Path(RAW_ROOT_DIR) / image_relpath
        if not image_path.exists():
            return {"session_id": sid, "image": None, "status": f"❌ Image file not found: {image_path}"}

        image = load_image(str(image_path), max_size=LABELING_MAX_SIZE)
        self.sessions[sid] = {
            "image_id": image_id,
            "image_path": str(image_path),
            "image_relpath": image_relpath,
            "product_id": product_id,
            "image_array": image,
            "points": [],
            "labels": [],
            "mask": None,
            "labeler_id": labeler_id,
        }
        # Non-blocking warmup so Load/Save remains fast.
        if PRECOMPUTE_ON_LOAD:
            self._warmup_segmenter_async(int(image_id), image)
        stats = db.get_stats()
        return {
            "session_id": sid,
            "image": _image_to_b64_png(image),
            "product_id": product_id,
            "status": (
                f"✅ Loaded image {image_id}\nPath: {image_relpath}\n"
                f"Remaining: {stats['unlabeled_images']} unlabeled images"
            ),
        }

    def add_point(self, session_id: str, x: int, y: int) -> dict[str, Any]:
        state = self.sessions.get(session_id, {})
        if "image_array" not in state:
            return {"session_id": session_id, "image": None, "status": "❌ No image loaded"}

        state["points"].append([x, y])
        state["labels"].append(1)
        try:
            segmenter = self._get_segmenter()
            image_id = int(state["image_id"])
            # Performance optimization:
            # SAM2 set_image() computes heavy image embeddings. Reuse them while
            # the user is clicking multiple points on the same loaded image.
            if self._segmenter_loaded_image_id != image_id:
                segmenter.set_image(state["image_array"])
                self._segmenter_loaded_image_id = image_id
            point_coords = np.array(state["points"])
            point_labels = np.array(state["labels"])
            masks, scores, _ = segmenter.segment_with_points(point_coords, point_labels, multimask_output=True)
            best_idx = np.argmax(scores)
            mask = masks[best_idx]
            state["mask"] = mask

            overlay = apply_mask_overlay(state["image_array"], mask, alpha=config.MASK_ALPHA, color=config.MASK_COLOR)
            overlay_pil = Image.fromarray(overlay)
            draw = ImageDraw.Draw(overlay_pil)
            for pt in state["points"]:
                draw.ellipse([pt[0] - 5, pt[1] - 5, pt[0] + 5, pt[1] + 5], fill="red", outline="white")
            self.sessions[session_id] = state
            return {
                "session_id": session_id,
                "image": _image_to_b64_png(np.array(overlay_pil)),
                "status": f"✅ Point added at ({x}, {y})\nTotal points: {len(state['points'])}\nMask score: {scores[best_idx]:.3f}",
            }
        except Exception as e:
            # Keep backend running even if SAM2 is unavailable; report actionable error on segmentation call.
            return {
                "session_id": session_id,
                "image": _image_to_b64_png(state.get("image_array")),
                "status": f"❌ Segmentation failed: {str(e)}",
            }

    def auto_annotate_product(
        self,
        image_id: int,
        image: np.ndarray,
        mask: np.ndarray,
        product_id: int,
    ) -> None:
        """Auto-annotate remaining unlabeled images of the same product using DINOv2 matching."""
        if not AUTO_ANNOTATE_ENABLED:
            print("[AutoAnnotate] Disabled via AUTO_ANNOTATE_ENABLED=0")
            return
        try:
            ref_embedding = self._get_embedder().compute_ffa_embedding(image, mask)

            sibling_images = db.get_images_by_product(
                product_id, exclude_statuses=["labeled", "skipped", "proposed"]
            )
            targets = [(iid, rp) for iid, rp, _ in sibling_images if iid != image_id]

            if not targets:
                print(f"[AutoAnnotate] No unlabeled siblings for product {product_id}")
                return

            if len(targets) > MAX_AUTO_ANNOTATE_SIBLINGS:
                print(f"[AutoAnnotate] Too many siblings ({len(targets)} > {MAX_AUTO_ANNOTATE_SIBLINGS}), skipping")
                return

            print(f"[AutoAnnotate] Auto-annotating {len(targets)} images for product {product_id}")

            masks_dir = Path(OUTPUT_ROOT_DIR) / "masks"
            cutouts_dir = Path(OUTPUT_ROOT_DIR) / "cutouts"
            overlays_dir = Path(OUTPUT_ROOT_DIR) / "overlays"
            masks_dir.mkdir(parents=True, exist_ok=True)
            cutouts_dir.mkdir(parents=True, exist_ok=True)
            overlays_dir.mkdir(parents=True, exist_ok=True)

            for target_id, target_relpath in targets:
                try:
                    target_path = Path(RAW_ROOT_DIR) / target_relpath
                    if not target_path.exists():
                        print(f"[AutoAnnotate] File not found: {target_path}")
                        continue

                    target_image = load_image(str(target_path), max_size=LABELING_MAX_SIZE)
                    result = self._get_matcher().match_in_image(
                        target_image, ref_embedding, str(target_path)
                    )

                    if not result.best_match or result.best_match.similarity < 0.7:
                        print(f"[AutoAnnotate] No confident match for image {target_id} "
                              f"(best={result.best_match.similarity:.3f if result.best_match else 'N/A'})")
                        continue

                    best = result.best_match

                    mask_filename = f"{target_id}.png"
                    mask_path = masks_dir / mask_filename
                    mask_relpath = f"masks/{mask_filename}"
                    Image.fromarray((best.mask * 255).astype(np.uint8)).save(mask_path)

                    cutout_filename = f"{target_id}_white.jpg"
                    cutout_path = cutouts_dir / cutout_filename
                    cutout_relpath = f"cutouts/{cutout_filename}"
                    mask_3ch = np.stack([best.mask] * 3, axis=-1)
                    white_bg = np.ones_like(target_image) * 255
                    cutout = np.where(mask_3ch, target_image, white_bg)
                    Image.fromarray(cutout.astype(np.uint8)).save(cutout_path)

                    overlay_filename = f"{target_id}_overlay.jpg"
                    overlay_path = overlays_dir / overlay_filename
                    overlay_relpath = f"overlays/{overlay_filename}"
                    overlay = apply_mask_overlay(target_image, best.mask)
                    Image.fromarray(overlay).save(overlay_path)

                    db.save_label(
                        image_id=target_id,
                        packaging="",
                        product_name="",
                        mask_relpath=mask_relpath,
                        cutout_relpath=cutout_relpath,
                        overlay_relpath=overlay_relpath,
                        similarity_score=best.similarity,
                        created_by="auto",
                        status="proposed",
                    )
                    print(f"[AutoAnnotate] Proposed label for image {target_id} "
                          f"(similarity={best.similarity:.3f})")

                except Exception as e:
                    print(f"[AutoAnnotate] Failed for image {target_id}: {e}")
                    continue

        except Exception as e:
            print(f"[AutoAnnotate] Auto-annotation failed: {e}")

    def get_proposed(self, product_id: int | None = None) -> list[dict]:
        """Return all proposed labels with overlay image as base64, optionally filtered by product."""
        rows = db.get_proposed_labels(product_id)
        result = []
        for row in rows:
            overlay_b64 = None
            if row.get("overlay_relpath"):
                overlay_path = Path(OUTPUT_ROOT_DIR) / row["overlay_relpath"]
                if overlay_path.exists():
                    try:
                        img = Image.open(overlay_path).convert("RGB")
                        overlay_b64 = _image_to_b64_png(np.array(img))
                    except Exception:
                        pass
            result.append({
                **row,
                "overlay_b64": overlay_b64,
            })
        return result

    def accept_proposed(
        self, label_id: int, packaging: str, product_name: str, labeler_id: str
    ) -> dict[str, Any]:
        """Accept a single proposed label."""
        try:
            db.confirm_label(label_id, packaging, product_name, confirmed_by=labeler_id)
            return {"ok": True, "label_id": label_id, "status": f"✅ Accepted label {label_id}"}
        except Exception as e:
            return {"ok": False, "label_id": label_id, "status": f"❌ {e}"}

    def reject_proposed(
        self, image_id: int
    ) -> dict[str, Any]:
        """Reject a proposed label and return image to unlabeled queue."""
        try:
            db.reject_proposed_label(image_id)
            return {"ok": True, "image_id": image_id, "status": f"🗑️ Rejected, image {image_id} back to queue"}
        except Exception as e:
            return {"ok": False, "image_id": image_id, "status": f"❌ {e}"}

    def accept_all_proposed(
        self, product_id: int, packaging: str, product_name: str, labeler_id: str
    ) -> dict[str, Any]:
        """Accept all proposed labels for a product in one shot."""
        rows = db.get_proposed_labels(product_id)
        accepted, failed = 0, 0
        for row in rows:
            try:
                db.confirm_label(
                    row["label_id"], packaging, product_name, confirmed_by=labeler_id
                )
                accepted += 1
            except Exception as e:
                print(f"[AcceptAll] Failed label {row['label_id']}: {e}")
                failed += 1
        return {
            "ok": True,
            "accepted": accepted,
            "failed": failed,
            "status": f"✅ Accepted {accepted} proposed labels" + (f" ({failed} failed)" if failed else ""),
        }

    def reset(self, session_id: str) -> dict[str, Any]:
        state = self.sessions.get(session_id, {})
        if "image_array" not in state:
            return {"session_id": session_id, "image": None, "status": "❌ No image loaded"}
        state["points"] = []
        state["labels"] = []
        state["mask"] = None
        return {"session_id": session_id, "image": _image_to_b64_png(state["image_array"]), "status": "✅ Image reset"}

    def skip_and_next(self, session_id: str, labeler_id: str, reason: str) -> dict[str, Any]:
        state = self.sessions.get(session_id, {})
        if "image_id" not in state:
            return {"session_id": session_id, "image": None, "status": "❌ No image loaded to skip"}
        image_id = state["image_id"]
        skipped_by = state.get("labeler_id", labeler_id or "anonymous")
        db.mark_image_skipped(image_id=image_id, skipped_by=skipped_by, reason=reason)
        nxt = self.load_next(labeler_id, session_id)
        nxt["status"] = f"⏭️ Skipped image {image_id} (reason: {reason})\n\n{nxt['status']}"
        return nxt

    def save_and_next(self, session_id: str, packaging: str, product_name: str) -> dict[str, Any]:
        state = self.sessions.get(session_id, {})
        if "image_id" not in state:
            return {"session_id": session_id, "image": None, "status": "❌ No image loaded"}
        if state.get("mask") is None:
            return {
                "session_id": session_id,
                "image": _image_to_b64_png(state.get("image_array")),
                "status": "❌ No mask created. Click on the product first.",
            }

        image_id = state["image_id"]
        labeler_id = state.get("labeler_id", "anonymous")
        masks_dir = Path(OUTPUT_ROOT_DIR) / "masks"
        cutouts_dir = Path(OUTPUT_ROOT_DIR) / "cutouts"
        overlays_dir = Path(OUTPUT_ROOT_DIR) / "overlays"
        masks_dir.mkdir(parents=True, exist_ok=True)
        cutouts_dir.mkdir(parents=True, exist_ok=True)
        overlays_dir.mkdir(parents=True, exist_ok=True)

        mask_filename = f"{image_id}.png"
        mask_path = masks_dir / mask_filename
        mask_relpath = f"masks/{mask_filename}"
        Image.fromarray((state["mask"] * 255).astype(np.uint8)).save(mask_path)

        cutout_filename = f"{image_id}_white.jpg"
        cutout_path = cutouts_dir / cutout_filename
        cutout_relpath = f"cutouts/{cutout_filename}"
        image_rgb = state["image_array"]
        mask_3ch = np.stack([state["mask"]] * 3, axis=-1)
        white_bg = np.ones_like(image_rgb) * 255
        cutout = np.where(mask_3ch, image_rgb, white_bg)
        Image.fromarray(cutout.astype(np.uint8)).save(cutout_path)

        overlay_filename = f"{image_id}_overlay.jpg"
        overlay_path = overlays_dir / overlay_filename
        overlay_relpath = f"overlays/{overlay_filename}"
        overlay = apply_mask_overlay(image_rgb, state["mask"])
        Image.fromarray(overlay).save(overlay_path)

        db.save_label(
            image_id=image_id,
            packaging=packaging,
            product_name=product_name,
            mask_relpath=mask_relpath,
            cutout_relpath=cutout_relpath,
            overlay_relpath=overlay_relpath,
            similarity_score=None,
            created_by=labeler_id,
            status="confirmed",
        )

        threading.Thread(
            target=self.auto_annotate_product,
            kwargs={
                "image_id": image_id,
                "image": state["image_array"].copy(),
                "mask": state["mask"].copy(),
                "product_id": state["product_id"],
            },
            daemon=True,
        ).start()

        nxt = self.load_next(labeler_id, session_id)
        nxt["status"] = (
            f"✅ Saved label for image {image_id}\nPackaging: {packaging}\nProduct: {product_name}\n\n{nxt['status']}"
        )
        return nxt
