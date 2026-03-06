#!/usr/bin/env python3
"""
Gradio Labeling UI for Product Segmentation System

This UI provides:
1. Manual upload of product folders (ZIP)
2. Load next unlabeled image from database
3. Interactive point/box selection for SAM2 segmentation
4. Save results to disk + database
5. Automatic load next after save

Environment variables:
- DATABASE_URL: PostgreSQL connection string (required)
- RAW_ROOT_DIR: Root directory for raw product images (default: /data/raw_products)
- OUTPUT_ROOT_DIR: Root directory for output files (default: /data/labels_output)
- LOCK_MINUTES: Lock timeout in minutes (default: 30)
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import zipfile
import tempfile
import shutil
from typing import Optional, Tuple, Dict, Any
import numpy as np
from PIL import Image
import gradio as gr

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ean_system import db, config
from ean_system.pipeline import ProductSegmentationPipeline
from ean_system.sam2_segmenter import SAM2InteractiveSegmenter
from ean_system.image_utils import load_image, apply_mask_overlay

# Configuration from environment
RAW_ROOT_DIR = os.getenv('RAW_ROOT_DIR', '/data/raw_products')
OUTPUT_ROOT_DIR = os.getenv('OUTPUT_ROOT_DIR', '/data/labels_output')
LOCK_MINUTES = int(os.getenv('LOCK_MINUTES', '30'))

# Ensure output directories exist
Path(OUTPUT_ROOT_DIR).mkdir(parents=True, exist_ok=True)
Path(RAW_ROOT_DIR).mkdir(parents=True, exist_ok=True)

# Global pipeline instance (lazy loaded)
_pipeline = None
_segmenter = None


def get_pipeline():
    """Get or create pipeline instance."""
    global _pipeline
    if _pipeline is None:
        _pipeline = ProductSegmentationPipeline(
            similarity_threshold=0.65,
            top_k=3
        )
        _pipeline._ensure_models()
    return _pipeline


def get_segmenter():
    """Get or create segmenter instance."""
    global _segmenter
    if _segmenter is None:
        _segmenter = SAM2InteractiveSegmenter()
    return _segmenter


def upload_and_ingest(zip_file, uploader_name: str) -> str:
    """
    Handle ZIP upload, extract to RAW_ROOT_DIR, and ingest into database.
    
    Args:
        zip_file: Gradio File object
        uploader_name: Name of person uploading (optional)
    
    Returns:
        Status message
    """
    if zip_file is None:
        return "❌ No file uploaded"
    
    try:
        # Create temp directory for extraction
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Extract ZIP
            with zipfile.ZipFile(zip_file.name, 'r') as zip_ref:
                # Security check: prevent zip slip
                for member in zip_ref.namelist():
                    member_path = temp_path / member
                    if not str(member_path.resolve()).startswith(str(temp_path.resolve())):
                        return f"❌ Security error: Invalid path in ZIP: {member}"
                
                zip_ref.extractall(temp_path)
            
            # Find the top-level folder
            extracted_items = list(temp_path.iterdir())
            if len(extracted_items) == 0:
                return "❌ ZIP file is empty"
            
            # If there's a single top-level folder, use it; otherwise use all items
            if len(extracted_items) == 1 and extracted_items[0].is_dir():
                product_folder = extracted_items[0]
            else:
                # Create a wrapper folder
                product_folder = temp_path / "uploaded_product"
                product_folder.mkdir()
                for item in extracted_items:
                    shutil.move(str(item), str(product_folder))
            
            product_name = product_folder.name
            
            # Check if product already exists, add suffix if needed
            target_path = Path(RAW_ROOT_DIR) / product_name
            counter = 1
            while target_path.exists():
                target_path = Path(RAW_ROOT_DIR) / f"{product_name}_{counter}"
                counter += 1
            
            # Move to RAW_ROOT_DIR
            shutil.move(str(product_folder), str(target_path))
            
            # Ingest into database
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
    
    except zipfile.BadZipFile:
        return "❌ Invalid ZIP file"
    except Exception as e:
        return f"❌ Upload failed: {str(e)}"


def load_next(labeler_id: str, state: Dict) -> Tuple[Any, Dict, str]:
    """
    Load next unlabeled image from database.
    
    Args:
        labeler_id: Identifier for the labeler
        state: Current state dict
    
    Returns:
        (image, new_state, status_message)
    """
    if not labeler_id:
        labeler_id = "anonymous"
    
    try:
        # Check database connectivity
        if not db.healthcheck():
            return None, {}, "❌ Database connection failed"
        
        # Get next unlabeled image
        result = db.get_next_unlabeled_image(labeler_id, LOCK_MINUTES)
        
        if result is None:
            stats = db.get_stats()
            return None, {}, (
                f"🎉 No more unlabeled images!\n\n"
                f"Database stats:\n"
                f"  Total images: {stats['total_images']}\n"
                f"  Labeled: {stats['labeled_images']}\n"
                f"  Unlabeled: {stats['unlabeled_images']}"
            )
        
        image_id, image_relpath, product_id = result
        
        # Load image from disk
        image_path = Path(RAW_ROOT_DIR) / image_relpath
        if not image_path.exists():
            return None, {}, f"❌ Image file not found: {image_path}"
        
        image = load_image(str(image_path))
        
        # Create new state
        new_state = {
            'image_id': image_id,
            'image_path': str(image_path),
            'image_relpath': image_relpath,
            'product_id': product_id,
            'image_array': image,
            'points': [],
            'labels': [],
            'mask': None,
            'labeler_id': labeler_id
        }
        
        stats = db.get_stats()
        status = (
            f"✅ Loaded image {image_id}\n"
            f"Path: {image_relpath}\n"
            f"Remaining: {stats['unlabeled_images']} unlabeled images"
        )
        
        return image, new_state, status
        
    except Exception as e:
        return None, {}, f"❌ Error loading next image: {str(e)}"


def add_point(state: Dict, evt: gr.SelectData) -> Tuple[Any, Dict, str]:
    """
    Add a point click for SAM2 segmentation.
    
    Args:
        state: Current state
        evt: Gradio click event with coordinates
    
    Returns:
        (updated_image, new_state, status)
    """
    if not state or 'image_array' not in state:
        return None, state, "❌ No image loaded"
    
    try:
        x, y = evt.index[0], evt.index[1]
        
        # Add point (positive label = 1)
        state['points'].append([x, y])
        state['labels'].append(1)
        
        # Run SAM2 segmentation
        segmenter = get_segmenter()
        segmenter.set_image(state['image_array'])
        
        point_coords = np.array(state['points'])
        point_labels = np.array(state['labels'])
        
        masks, scores, logits = segmenter.segment_with_points(
            point_coords, point_labels, multimask_output=True
        )
        
        # Use best mask
        best_idx = np.argmax(scores)
        mask = masks[best_idx]
        state['mask'] = mask
        
        # Create overlay visualization
        overlay = apply_mask_overlay(
            state['image_array'],
            mask,
            alpha=config.MASK_ALPHA,
            mask_color=config.MASK_COLOR
        )
        
        # Draw points on overlay
        overlay_pil = Image.fromarray(overlay)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(overlay_pil)
        for pt in state['points']:
            draw.ellipse([pt[0]-5, pt[1]-5, pt[0]+5, pt[1]+5], fill='red', outline='white')
        
        status = (
            f"✅ Point added at ({x}, {y})\n"
            f"Total points: {len(state['points'])}\n"
            f"Mask score: {scores[best_idx]:.3f}"
        )
        
        return np.array(overlay_pil), state, status
        
    except Exception as e:
        return state.get('image_array'), state, f"❌ Segmentation failed: {str(e)}"


def save_and_next(
    state: Dict,
    packaging: str,
    product_name: str
) -> Tuple[Any, Dict, str, str, str]:
    """
    Save current label to disk + database, then load next image.
    
    Returns:
        (image, new_state, status, packaging_cleared, product_name_cleared)
    """
    if not state or 'image_id' not in state:
        return None, {}, "❌ No image loaded", "", ""
    
    if state.get('mask') is None:
        return state.get('image_array'), state, "❌ No mask created. Click on the product first.", packaging, product_name
    
    try:
        image_id = state['image_id']
        labeler_id = state.get('labeler_id', 'anonymous')
        
        # Create output paths (relative to OUTPUT_ROOT_DIR)
        masks_dir = Path(OUTPUT_ROOT_DIR) / 'masks'
        cutouts_dir = Path(OUTPUT_ROOT_DIR) / 'cutouts'
        overlays_dir = Path(OUTPUT_ROOT_DIR) / 'overlays'
        
        masks_dir.mkdir(parents=True, exist_ok=True)
        cutouts_dir.mkdir(parents=True, exist_ok=True)
        overlays_dir.mkdir(parents=True, exist_ok=True)
        
        # Save mask
        mask_filename = f"{image_id}.png"
        mask_path = masks_dir / mask_filename
        mask_relpath = f"masks/{mask_filename}"
        Image.fromarray((state['mask'] * 255).astype(np.uint8)).save(mask_path)
        
        # Save cutout (with white background)
        cutout_filename = f"{image_id}_white.jpg"
        cutout_path = cutouts_dir / cutout_filename
        cutout_relpath = f"cutouts/{cutout_filename}"
        
        # Create cutout with white background
        image_rgb = state['image_array']
        mask_3ch = np.stack([state['mask']] * 3, axis=-1)
        white_bg = np.ones_like(image_rgb) * 255
        cutout = np.where(mask_3ch, image_rgb, white_bg)
        Image.fromarray(cutout.astype(np.uint8)).save(cutout_path)
        
        # Save overlay (optional)
        overlay_filename = f"{image_id}_overlay.jpg"
        overlay_path = overlays_dir / overlay_filename
        overlay_relpath = f"overlays/{overlay_filename}"
        overlay = apply_mask_overlay(image_rgb, state['mask'])
        Image.fromarray(overlay).save(overlay_path)
        
        # Save to database
        db.save_label(
            image_id=image_id,
            packaging=packaging,
            product_name=product_name,
            mask_relpath=mask_relpath,
            cutout_relpath=cutout_relpath,
            overlay_relpath=overlay_relpath,
            similarity_score=None,
            created_by=labeler_id
        )
        
        # Load next image
        next_img, next_state, next_status = load_next(labeler_id, {})
        
        save_status = (
            f"✅ Saved label for image {image_id}\n"
            f"Packaging: {packaging}\n"
            f"Product: {product_name}\n\n"
            f"{next_status}"
        )
        
        # Clear input fields
        return next_img, next_state, save_status, "", ""
        
    except Exception as e:
        return state.get('image_array'), state, f"❌ Save failed: {str(e)}", packaging, product_name


def reset_image(state: Dict) -> Tuple[Any, Dict, str]:
    """Reset current image to original (clear points and mask)."""
    if not state or 'image_array' not in state:
        return None, {}, "❌ No image loaded"
    
    state['points'] = []
    state['labels'] = []
    state['mask'] = None
    
    return state['image_array'], state, "✅ Image reset"


def skip_image_and_next(
    state: Dict,
    labeler_id: str,
    reason: str = "not_clear"
) -> Tuple[Any, Dict, str]:
    """
    Mark current image as skipped and load next unlabeled image.
    
    Args:
        state: Current state with image_id
        labeler_id: Identifier for the labeler
        reason: Reason for skipping (default: "not_clear")
    
    Returns:
        (next_image, new_state, status_message)
    """
    if not state or 'image_id' not in state:
        return None, {}, "❌ No image loaded to skip"
    
    try:
        image_id = state['image_id']
        skipped_by = state.get('labeler_id', labeler_id or 'anonymous')
        
        # Mark current image as skipped in database
        db.mark_image_skipped(
            image_id=image_id,
            skipped_by=skipped_by,
            reason=reason
        )
        
        # Load next unlabeled image
        next_img, next_state, next_status = load_next(labeler_id, {})
        
        skip_status = (
            f"⏭️ Skipped image {image_id} (reason: {reason})\n\n"
            f"{next_status}"
        )
        
        return next_img, next_state, skip_status
        
    except Exception as e:
        return None, {}, f"❌ Skip failed: {str(e)}"


def build_ui():
    """Build and launch Gradio UI."""
    
    # Initialize database
    try:
        db.init_db()
        if db.healthcheck():
            print("✅ Database connected")
        else:
            print("❌ Database connection failed")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
    
    with gr.Blocks(title="Product Labeling System") as demo:
        gr.Markdown("# 🏷️ Product Labeling System")
        gr.Markdown("SAM2 + DINOv2 based product segmentation with database persistence")
        
        # State
        state = gr.State({})
        
        # Upload section
        with gr.Accordion("📤 Upload Product Folder", open=False):
            gr.Markdown("""
            Upload a ZIP file containing a product folder with images.
            The ZIP should contain one top-level folder with product images inside.
            """)
            with gr.Row():
                upload_file = gr.File(label="Upload .zip file", file_types=[".zip"])
                uploader_name = gr.Textbox(label="Your name (optional)", placeholder="e.g., John")
            upload_btn = gr.Button("Upload & Ingest", variant="primary")
            upload_status = gr.Textbox(label="Upload Status", lines=8)
        
        upload_btn.click(
            fn=upload_and_ingest,
            inputs=[upload_file, uploader_name],
            outputs=[upload_status]
        )
        
        gr.Markdown("---")
        
        # Labeling section
        gr.Markdown("## 🖼️ Labeling Interface")
        
        with gr.Row():
            labeler_id_input = gr.Textbox(
                label="Labeler ID",
                placeholder="Enter your name/ID",
                value="anonymous"
            )
            load_btn = gr.Button("Load Next Image", variant="primary")
        
        status_box = gr.Textbox(label="Status", lines=4)
        
        with gr.Row():
            with gr.Column(scale=2):
                image_display = gr.Image(
                    label="Click on product to segment",
                    type="numpy",
                    interactive=True
                )
                
                with gr.Row():
                    reset_btn = gr.Button("Reset Image")
                    skip_btn = gr.Button("Skip (Not clear) → Next", variant="secondary")
            
            with gr.Column(scale=1):
                gr.Markdown("### Label Information")
                packaging_input = gr.Textbox(
                    label="Packaging Type",
                    placeholder="e.g., box, bottle, bag"
                )
                product_name_input = gr.Textbox(
                    label="Product Name",
                    placeholder="e.g., Milk 1L"
                )
                
                save_btn = gr.Button("Save & Load Next", variant="primary")
                
                gr.Markdown("### Instructions")
                gr.Markdown("""
                1. Click **Load Next Image**
                2. Click on the product to segment
                3. Fill in packaging and product name
                4. Click **Save & Load Next**
                
                **Tips:**
                - Click multiple times to refine mask
                - Use Reset to start over
                - Use **Skip** for blurry/unclear images
                """)
        
        # Event handlers
        load_btn.click(
            fn=load_next,
            inputs=[labeler_id_input, state],
            outputs=[image_display, state, status_box]
        )
        
        image_display.select(
            fn=add_point,
            inputs=[state],
            outputs=[image_display, state, status_box]
        )
        
        reset_btn.click(
            fn=reset_image,
            inputs=[state],
            outputs=[image_display, state, status_box]
        )
        
        skip_btn.click(
            fn=lambda: "⏭️ Skipping current image as NOT CLEAR and loading next...",
            outputs=[status_box]
        ).then(
            fn=skip_image_and_next,
            inputs=[state, labeler_id_input],
            outputs=[image_display, state, status_box]
        )
        
        save_btn.click(
            fn=save_and_next,
            inputs=[state, packaging_input, product_name_input],
            outputs=[image_display, state, status_box, packaging_input, product_name_input]
        )
    
    return demo


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Gradio Labeling UI')
    parser.add_argument(
        '--public',
        action='store_true',
        help='Get a public URL via ngrok (use if Gradio share link fails due to firewall/antivirus)',
    )
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    _u = os.environ.get("GRADIO_USERNAME")
    _p = os.environ.get("GRADIO_PASSWORD")
    if not _u or not _p:
        raise SystemExit("GRADIO_USERNAME and GRADIO_PASSWORD must be set (e.g. in .env).")

    demo = build_ui()
    _auth = [(_u, _p)]

    if args.public:
        import threading
        import time
        from pyngrok import ngrok

        def run_app():
            demo.launch(
                server_name="0.0.0.0",
                server_port=7860,
                share=False,
                auth=_auth,
            )

        thread = threading.Thread(target=run_app, daemon=True)
        thread.start()

        # Wait for server to be ready
        import socket
        for _ in range(30):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                s.connect(("127.0.0.1", 7860))
                s.close()
                break
            except (socket.error, OSError):
                time.sleep(1)
        else:
            print("Server failed to start on port 7860.")
            sys.exit(1)

        try:
            public_url = ngrok.connect(7860, "http")
            print("\n" + "=" * 60)
            print("PUBLIC URL (share with anyone):", public_url)
            print("=" * 60 + "\n")
        except Exception as e:
            print("ngrok failed:", e)
            print("Install/configure ngrok: pip install pyngrok")
            print("Or sign up at https://ngrok.com and add your auth token.")
            sys.exit(1)

        thread.join()
    else:
        demo.launch(
            server_name="0.0.0.0",
            server_port=7860,
            share=True,
            auth=_auth,
        )
