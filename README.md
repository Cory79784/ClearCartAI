# EAN / 360° Product Segmentation System

Segment a product in one image (click or bounding box), then automatically find and segment the **same product** across all other 360° camera images. Uses **SAM2** for segmentation and **DINOv2** for cross-image matching.

---

## Quick start

**Requirements:** Python 3.10+, CUDA-capable GPU (recommended), ~10GB disk for models.

```bash
# 1. Clone and enter project
cd ean_system_new

# 2. Create virtual environment (recommended)
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate

# 3. Install dependencies (see Setup below)
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install git+https://github.com/facebookresearch/sam2.git

# 1) Activate your venv (if you use one)
#    e.g.:
#    venv\Scripts\activate

# 2) Remove CPU-only PyTorch
pip uninstall -y torch torchvision torchaudio

# 3) Install CUDA build (matches setup.sh / README)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# 4) Verify CUDA is available
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
# should print True for cuda_is_available

# 4. Run interactive segmentation (from project root)
python scripts/run_interactive.py --image-dir ./path/to/your/images/ --output ./outputs
```

In the UI: **left-click** on the product, then press **Enter** to run. Results are written to `./outputs`.

---

## Project layout

```
ean_system_new/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── setup.sh                  # One-shot setup (Linux/macOS)
├── install_and_run_ui.sh     # Install + run Gradio UI (Linux/macOS)
├── install_and_run_ui.ps1    # Install + run Gradio UI (Windows)
│
├── ean_system/               # Core package (import as ean_system.xxx)
│   ├── __init__.py
│   ├── config.py             # Central config (paths, thresholds, device)
│   ├── db.py                 # Database layer (PostgreSQL) for labeling
│   ├── pipeline.py           # End-to-end pipeline
│   ├── sam2_segmenter.py     # SAM2 interactive + auto segmentation
│   ├── model_loader.py       # Lazy load SAM2 & DINOv2
│   ├── dinov2_embedder.py    # DINOv2 feature extraction (FFA)
│   ├── matcher.py            # Cross-image instance matching
│   ├── image_utils.py        # Load/resize images
│   ├── mask_utils.py         # Mask ops, NMS
│   ├── export.py             # Export masks, cutouts, visualizations
│   └── interactive_selector.py  # Click-to-segment UI (matplotlib)
│
├── scripts/                  # Entry-point scripts (run from project root)
│   ├── run_interactive.py    # Interactive: click product, match all images
│   ├── run_batch.py          # Batch: reference image + point/bbox, no UI
│   ├── run_interactive_verbose.py  # Same as interactive with step-by-step log
│   └── ingest_folders.py     # Ingest product folders into DB (for labeling UI)
│
├── tools/
│   └── label_ui_gradio.py    # Web labeling UI (Gradio + PostgreSQL)
│
├── tests/                    # Tests and sanity checks
│   ├── test_setup.py         # Verify env and imports
│   ├── test_single_product.py
│   ├── test_all_products.py
│   └── test_batch_interactive.py
│
├── docs/
│   ├── DEVELOPMENT_PLAN.md   # Architecture and design
│   └── CHANGELOG_2026-02-18.md
│
├── models/                   # Created at runtime
│   └── checkpoints/          # SAM2 weights (if not using HuggingFace)
└── outputs/                  # Default output directory
```

**Important:** Always run commands from the **project root** (`ean_system_new/`). Scripts add the project root to `sys.path` automatically.

---

## Setup

### Option A: Automated (Linux/macOS)

```bash
bash setup.sh
```

This creates a conda env (if available), installs PyTorch with CUDA, SAM2, and other deps, and pre-downloads model weights.

### Option B: Manual

1. **Python 3.10+** and a **CUDA-capable GPU** (or CPU for small tests).

2. **PyTorch with CUDA** (adjust cu121 to your CUDA version):
   ```bash
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
   ```

3. **SAM2** (from source):
   ```bash
   pip install git+https://github.com/facebookresearch/sam2.git
   ```

4. **Rest of dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **First run** will download DINOv2 and SAM2 weights (~10GB) via Hugging Face.

### Optional: Labeling UI (PostgreSQL + Gradio)

- Set `DATABASE_URL` (e.g. `postgresql://user:pass@localhost:5432/dbname`).
- Optionally set `RAW_ROOT_DIR`, `OUTPUT_ROOT_DIR`, `LOCK_MINUTES`.
- **Quick install and run:**
  - **Windows:** `.\install_and_run_ui.ps1` (or `--install-only` to only install).
  - **Linux/macOS:** `bash install_and_run_ui.sh` (or `--install-only` to only install).
- Or run manually:
  ```bash
  python tools/label_ui_gradio.py
  ```
- Ingest folders: `python scripts/ingest_folders.py --root /path/to/product/folders --init-db`

---

## Usage

### Interactive mode (click on product)

From **project root**:

```bash
# Images in a directory
python scripts/run_interactive.py --image-dir ./360_captures/ --output ./results/

# Or list files
python scripts/run_interactive.py --images img1.jpg img2.jpg img3.jpg --output ./results/

# Custom reference image and threshold
python scripts/run_interactive.py --image-dir ./captures/ --reference img_001.jpg --threshold 0.7 --output ./results/
```

**Controls:** Left-click = product point, Right-click = background (optional), **Enter** = confirm and run, **Q** = quit.

### Batch mode (no UI: point or bbox)

```bash
# Point prompt (x y on reference image)
python scripts/run_batch.py --image-dir ./360_captures/ --reference img_001.jpg --point 250 300 --output ./results/

# Bounding box (x1 y1 x2 y2)
python scripts/run_batch.py --image-dir ./360_captures/ --reference img_001.jpg --bbox 120 80 340 450 --output ./results/
```

### Verbose interactive (step-by-step log)

```bash
python scripts/run_interactive_verbose.py --image-dir ./my_images/ --output ./results/
```

### Verify setup

```bash
python tests/test_setup.py
```

Optional: set `TEST_IMAGE_DIR` to a folder with images to test image loading.

---

## Configuration

- **ean_system/config.py** — Paths and model/algorithm settings. Override via environment variables with prefix `PS_`, e.g.:
  - `PS_SIMILARITY_THRESHOLD=0.7`
  - `PS_DEVICE=cuda`
  - `PS_SAM2_CHECKPOINT=sam2.1_hiera_large.pt`
- **Paths:** `PROJECT_ROOT` is the directory containing `config.py`. Outputs go to `outputs/` by default; scripts accept `--output`.

---

## Outputs

For each run, the pipeline writes under the chosen output directory:

- **masks/** — Segmentation masks (PNG)
- **cutouts/** — Product cutouts (transparent background)
- **overlays/** — Visualizations (image + mask overlay)
- **gallery.jpg** — Summary gallery
- **summary.json** — Match statistics and paths

---

## Documentation

- **docs/LOCAL_AND_RUNPOD.md** — Run locally, deploy locally, and deploy on RunPod (single guide).
- **docs/RUNPOD.md** — RunPod-only deployment reference.
- **docs/DEVELOPMENT_PLAN.md** — Architecture, SAM2 + DINOv2 rationale, and module specs.
- **docs/CHANGELOG_2026-02-18.md** — Labeling UI and database changes.
- **docs/architecture.md** — New FastAPI + Next.js integration architecture.
- **docs/developer_guide.md** — How to run backend/frontend/Gradio.
- **docs/api_usage.md** — API endpoint reference.
- **docs/deployment_plan.md** — Deployment and AWS migration plan.
- **docs/migration_notes.md** — What changed and what remains.

---

## New Web Stack (FastAPI + Next.js)

Production-oriented web layers were added around the existing ML system:

- Backend: `backend/app` (FastAPI)
- Frontend: `frontend` (Next.js)
- Shared ML bridge: `backend/app/ml_bridge/adapter.py`
- Existing Gradio app remains available: `tools/label_ui_gradio.py`

### Backend quick start

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend quick start

```bash
cd frontend
npm install
npm run dev
```

### Security baseline in backend

- Authentication required for upload and jobs.
- Hardcoded admin login (phase requirement): `admin / nikhil@123`.
- Secure ZIP checks (size, members, zip-slip defense, image-type filtering).
- Queue-based async jobs with max **2** active inference jobs.

## License and credits

- **SAM2:** [facebookresearch/sam2](https://github.com/facebookresearch/sam2)
- **DINOv2:** [facebook/dinov2](https://github.com/facebookresearch/dinov2)

Check the respective repositories for their licenses.
