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


RAW_ROOT_DIR = os.getenv("RAW_ROOT_DIR", "/data/raw_products")
OUTPUT_ROOT_DIR = os.getenv("OUTPUT_ROOT_DIR", "/data/labels_output")
LOCK_MINUTES = int(os.getenv("LOCK_MINUTES", "30"))
LABELING_MAX_SIZE = int(os.getenv("LABELING_MAX_SIZE", "1024"))
PRECOMPUTE_ON_LOAD = os.getenv("PRECOMPUTE_ON_LOAD", "1") == "1"


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

    def upload_and_ingest(self, zip_path: Path, uploader_name: str) -> str:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                for member in zip_ref.namelist():
                    member_path = temp_path / member
                    if not str(member_path.resolve()).startswith(str(temp_path.resolve())):
                        return f"❌ Security error: Invalid path in ZIP: {member}"
                zip_ref.extractall(temp_path)

            extracted_items = list(temp_path.iterdir())
            if len(extracted_items) == 0:
                return "❌ ZIP file is empty"

            if len(extracted_items) == 1 and extracted_items[0].is_dir():
                product_folder = extracted_items[0]
            else:
                product_folder = temp_path / "uploaded_product"
                product_folder.mkdir()
                for item in extracted_items:
                    shutil.move(str(item), str(product_folder))

            product_name = product_folder.name
            target_path = Path(RAW_ROOT_DIR) / product_name
            counter = 1
            while target_path.exists():
                target_path = Path(RAW_ROOT_DIR) / f"{product_name}_{counter}"
                counter += 1

            shutil.move(str(product_folder), str(target_path))
            result = db.ingest_product_folder(RAW_ROOT_DIR, target_path.name)
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
        )

        nxt = self.load_next(labeler_id, session_id)
        nxt["status"] = (
            f"✅ Saved label for image {image_id}\nPackaging: {packaging}\nProduct: {product_name}\n\n{nxt['status']}"
        )
        return nxt
