# Run Locally, Deploy Locally, and RunPod

This guide covers three ways to use the EAN / 360° Product Segmentation System:

1. **Run on your local system** — one-time setup, then run scripts and/or the Gradio UI on your machine.
2. **Deploy on your local system** — run the app as a service (e.g., Gradio + PostgreSQL) on your own machine for ongoing use.
3. **Deploy on RunPod** — run the Gradio UI on a cloud GPU (hourly billing).

---

# Part I: Run on Your Local System

Use this when you want to run the pipeline or the labeling UI **on your own computer** for development or one-off jobs.

## 1.1 Requirements

- **Python** 3.10 or newer  
- **GPU** (recommended): NVIDIA with CUDA; **≥ 16 GB VRAM** for smooth use with default models  
- **RAM**: 16 GB+  
- **Disk**: ~10 GB for models (SAM2 + DINOv2 from Hugging Face), plus space for images and outputs  

Without a GPU, the app can run on CPU but will be slow.

## 1.2 One-time setup

### Option A: Install and run UI with a script (recommended)

From the **project root** (`ean_system_new/`):

- **Windows (PowerShell):**
  ```powershell
  cd ean_system_new
  .\install_and_run_ui.ps1
  ```
  To install only (no UI start): `.\install_and_run_ui.ps1 --install-only`  
  Set `$env:DATABASE_URL` before running if you use the labeling UI.

- **Linux / macOS:**
  ```bash
  cd ean_system_new
  bash install_and_run_ui.sh
  ```
  To install only: `bash install_and_run_ui.sh --install-only`  
  Set `export DATABASE_URL='...'` before running if you use the labeling UI.

The script creates a venv, installs dependencies, PyTorch (CUDA 12.1), and SAM2, then starts the Gradio UI on http://localhost:7860 (unless you pass `--install-only`).

### Option B: Manual setup

From the **project root** (`ean_system_new/`):

```bash
# 1. Create and activate a virtual environment
python -m venv venv

# Windows (PowerShell or CMD):
venv\Scripts\activate

# Linux / macOS:
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install PyTorch with CUDA (use cu118 or cu121 to match your CUDA version)
# Windows: 2>nul  |  Linux/macOS: 2>/dev/null
pip uninstall -y torch torchvision torchaudio 2>/dev/null || true
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# 4. Install SAM2 from source (--no-build-isolation uses your PyTorch; avoids re-downloading torch and disk space issues)
pip install --no-build-isolation "git+https://github.com/facebookresearch/sam2.git"
```

**Verify CUDA:**

```bash
python -c "import torch; print('CUDA:', torch.cuda.is_available())"
```

On first use, SAM2 and DINOv2 weights (~10 GB) are downloaded from Hugging Face automatically.

## 1.3 Run the pipeline (no web UI)

**Interactive mode** — click on the product in a matplotlib window, then run matching:

```bash
cd ean_system_new
python scripts/run_interactive.py --image-dir ./path/to/your/images/ --output ./outputs
```

- Left-click on the product → press **Enter** to run.  
- Results go to `./outputs` (masks, cutouts, overlays, `gallery.jpg`, `summary.json`).

**Batch mode** — no UI; you provide a point or bounding box:

```bash
# Point (x y on reference image)
python scripts/run_batch.py --image-dir ./360_captures/ --reference img_001.jpg --point 250 300 --output ./results/

# Bounding box (x1 y1 x2 y2)
python scripts/run_batch.py --image-dir ./360_captures/ --reference img_001.jpg --bbox 120 80 340 450 --output ./results/
```

## 1.4 Run the Gradio labeling UI locally

The web UI needs **PostgreSQL** and runs on port **7860**.

**1. Install and start PostgreSQL** (if not already running):

- **Windows**: Install [PostgreSQL](https://www.postgresql.org/download/windows/) and start the service.  
- **Linux**: e.g. `sudo apt install postgresql && sudo systemctl start postgresql`  
- **macOS**: e.g. `brew install postgresql && brew services start postgresql`  

Create a database and user, e.g.:

```sql
CREATE USER ean_user WITH PASSWORD 'your_password';
CREATE DATABASE ean_labels OWNER ean_user;
```

**2. Set environment variables** (PowerShell example; adjust for your shell):

```powershell
$env:DATABASE_URL = "postgresql://ean_user:your_password@localhost:5432/ean_labels"
$env:RAW_ROOT_DIR = "D:\data\raw_products"      # optional; default used if not set
$env:OUTPUT_ROOT_DIR = "D:\data\labels_output"   # optional
```

**3. Start the Gradio app** (from project root):

Either use the script (Option A above) or run manually:

```bash
cd ean_system_new
python tools/label_ui_gradio.py
```

Open **http://localhost:7860** in your browser. You can upload ZIPs, load images from the DB, click to segment with SAM2, and save labels.

**Optional — ingest existing folders into the DB:**

```bash
python scripts/ingest_folders.py --root D:\path\to\product\folders --init-db
```

### 1.5 Public URL — share the UI with anyone

By default, the app is reachable only on your machine (`http://localhost:7860`) or on your LAN (`http://YOUR_LOCAL_IP:7860`). To get a **public URL** that anyone can open from anywhere (no VPN, no same Wi‑Fi):

**What often goes wrong:**  
Gradio can create a temporary public link when you use `share=True`. On Windows, **Windows Defender or antivirus often blocks or deletes** the small tunnel program Gradio downloads (`frpc_windows_amd64.exe`), so you may see *"Could not create share link"* and no `https://....gradio.live` URL.

**Reliable fix — use the ngrok-based public URL:**

1. **Install the extra dependency** (one-time):
   ```bash
   pip install pyngrok
   ```

2. **Get an ngrok auth token** (one-time, free):
   - Sign up: https://ngrok.com/signup  
   - Copy your **authtoken**: https://dashboard.ngrok.com/get-started/your-authtoken  
   - Set it (PowerShell, per session; or add to your user environment variables):
     ```powershell
     $env:NGROK_AUTHTOKEN="your_token_here"
     ```
   - Linux/macOS: `export NGROK_AUTHTOKEN="your_token_here"`

3. **Run the UI with a public URL:**
   ```bash
   python tools/label_ui_gradio.py --public
   ```

   When the app is up, the terminal prints something like:
   ```text
   ============================================================
   PUBLIC URL (share with anyone): https://xxxx-xx-xx-xx-xx.ngrok-free.app
   ============================================================
   ```
   Share that **https://....ngrok-free.app** link; anyone can open it from anywhere.

**Optional — try Gradio’s built-in share again:**  
If you prefer Gradio’s link (`https://....gradio.live`), you can:
- Add a **Windows Security exclusion** for the folder where Gradio stores the tunnel (often under your user `AppData` or the project directory), or  
- Temporarily disable **Real-time protection** and run without `--public`:
  ```bash
  python tools/label_ui_gradio.py
  ```
  If you still see *"Could not create share link"*, use `--public` and the ngrok URL instead.

---

# Part II: Deploy on Your Local System

“Deploy locally” means running the app **as a service** on your machine so it stays on and is easy to start/stop (e.g., after a reboot).

## 2.1 What to run

- **Gradio labeling UI**: `python tools/label_ui_gradio.py` (port 7860)  
- **PostgreSQL**: required for the labeling UI; can run on the same machine or another.

## 2.2 Option A: Manual deployment (your machine)

1. **PostgreSQL**  
   - Install and run PostgreSQL (see 1.4).  
   - Create database and user; note `DATABASE_URL`.

2. **Persistent env vars**  
   Set them in your shell profile or a small script you source before starting the app, e.g.:

   - `DATABASE_URL` — required  
   - `RAW_ROOT_DIR`, `OUTPUT_ROOT_DIR` — optional (defaults in code)  
   - `PS_DEVICE=cuda`, `PS_DTYPE=bfloat16` — optional

3. **Start the UI** (from project root):

   ```bash
   cd ean_system_new
   venv\Scripts\activate   # or source venv/bin/activate
   python tools/label_ui_gradio.py
   ```

4. **Access**  
   - Same machine: http://localhost:7860  
   - Other devices on your LAN: http://YOUR_LOCAL_IP:7860 (app already binds to `0.0.0.0`)

5. **Keep it running**  
   - Run in a terminal that stays open, or  
   - Use a process manager (e.g. Windows Task Scheduler, systemd, or PM2) to run the same command and restart on failure.

## 2.3 Option B: PostgreSQL in Docker (local)

If you prefer to run only PostgreSQL in Docker:

```bash
docker run -d --name ean-postgres -e POSTGRES_USER=ean_user -e POSTGRES_PASSWORD=your_password -e POSTGRES_DB=ean_labels -p 5432:5432 postgres:15
```

Then set:

```text
DATABASE_URL=postgresql://ean_user:your_password@localhost:5432/ean_labels
```

Run the Gradio app **on the host** (not in Docker) so it can use your local GPU:

```bash
cd ean_system_new
python tools/label_ui_gradio.py
```

## 2.4 Optional: Run Gradio in Docker on your machine

If you want the whole app in Docker on your local GPU:

- Use a **CUDA-enabled base image** (e.g. `nvidia/cuda:12.1-runtime` or a PyTorch image).  
- Install Python, dependencies, PyTorch with CUDA, and SAM2 inside the image.  
- Use `--gpus all` when running the container so the app can use the GPU.  
- Mount a volume for `RAW_ROOT_DIR` and `OUTPUT_ROOT_DIR`.  
- Pass `DATABASE_URL` (and optional env vars) into the container.  
- Expose port **7860** and start with `python tools/label_ui_gradio.py`.

The exact Dockerfile and `docker run` depend on your OS and GPU drivers; the steps in Part I (dependencies, SAM2, PyTorch CUDA) are the same inside the image.

---

# Part III: Deploy on RunPod

Run the Gradio labeling UI on a **RunPod GPU pod** with hourly billing. Same app as locally; only the environment and access differ.

## 3.1 What runs on RunPod

- **Labeling UI**: `tools/label_ui_gradio.py` — Gradio on port **7860**.  
- **Optional**: `scripts/run_interactive.py`, `run_batch.py` for one-off jobs on the same pod.

## 3.2 Hardware requirements (RunPod)

- **GPU**: **≥ 16 GB VRAM** (e.g. T4 16GB, L4 24GB, A10G 24GB). **24 GB** recommended for headroom.  
- **RAM**: **≥ 16 GB**  
- **Disk**: **≥ 30–50 GB** (models + env + data)  
- **Python**: 3.10+  
- **CUDA**: Image with CUDA 12.x (e.g. PyTorch + CUDA 12.1 template)

## 3.3 RunPod template and pod setup

1. Create a **Secure Cloud** pod.  
2. Choose a **PyTorch + CUDA 12.x** template.  
3. Select a GPU with **≥ 16 GB VRAM**.  
4. Set **vCPU**: 4+, **RAM**: 16–32 GB, **Disk**: 50+ GB.  
5. Mount a **persistent volume** (e.g. at `/data`) for raw images and labels.

### 3.3a One-shot setup script (recommended for beginners)

After the pod is running, clone the repo and run a **single script** to install dependencies, configure the database (SQLite inside the repo on `/workspace`), and start the Gradio UI. If something is already installed, that step is skipped.

```bash
cd /workspace
git clone https://github.com/NIKHILSOURI/ClearCartAI.git
cd ClearCartAI
bash setup_and_run_pod.sh
```

The script will:

1. Check persistence (writes a test file under `/workspace`).
2. Clone the repo if it isn’t there (no-op if you already cloned).
3. Create and activate a venv if missing.
4. Install dependencies (requirements, PyTorch cu121, SAM2); **skips** if already installed.
5. Create `data/db/`, `data/raw/`, `outputs/` and set:
   - `DATABASE_URL=sqlite:////workspace/ClearCartAI/data/db/labeling.db`
   - `RAW_ROOT_DIR=/workspace/ClearCartAI/data/raw`
   - `OUTPUT_ROOT_DIR=/workspace/ClearCartAI/outputs`
   - Optional: `PS_DEVICE=cuda`, `PS_DTYPE=bfloat16`
6. Print a short sanity check (env vars, CUDA).
7. Start the Gradio UI on **0.0.0.0:7860** (reachable via RunPod’s HTTP port mapping).

Each time you create a new pod, run the same two commands (clone + `bash setup_and_run_pod.sh`). Everything persists under `/workspace` if that is your persistent volume. To only install and configure without starting the UI, run `bash setup_and_run_pod.sh --install-only`.

## 3.4 Directory layout in the pod

From the pod shell:

```bash
cd /workspace
git clone <YOUR_REPO_URL>
cd Ean-System/ean_system_new
```

Project root = `ean_system_new/`.

## 3.5 Database on RunPod — where it’s stored

The labeling UI needs a database for products, images, and labels. You can use **SQLite** (single file, good for one pod) or **PostgreSQL** (for multi-pod or existing Postgres).

### Option A: SQLite on your persistent volume (recommended for one pod)

**Where it’s stored:** One file, e.g. `/data/labeling.db` on your mounted volume. Survives pod restarts as long as the volume is mounted at `/data`.

1. In RunPod, **mount a persistent volume** at `/data` (or another path you prefer).
2. Set in the pod environment or before starting the app:

```bash
export DATABASE_URL="sqlite:////data/labeling.db"
```

(Use four slashes: `sqlite:///` + absolute path `/data/labeling.db`.)

3. Create the directory if needed: `mkdir -p /data`
4. Start the UI as usual; the app will create the tables on first run.

**Summary:** Database file = `/data/labeling.db` (or whatever path you put in `DATABASE_URL`). Keep that path on your **persistent volume** so it isn’t lost when the pod is recreated.

### Option B: PostgreSQL (managed or separate pod)

**Where it’s stored:** On the Postgres server (e.g. RunPod Postgres template, Neon, Supabase, or a second pod running Postgres). The RunPod app only connects to it; it doesn’t store the DB on the pod disk.

Set in the pod environment:

```text
DATABASE_URL=postgresql://user:password@db-host:5432/dbname
```

- **db-host**: IP or hostname of the Postgres server (must be reachable from the pod).
- Create the database and user on that server; the app creates tables on first run.

Use this if you want one database shared by several pods or already use Postgres.

### If you don’t set DATABASE_URL

The app falls back to **SQLite** at `ean_system_new/data/labeling.db` (inside the project directory). On RunPod that path is usually on **ephemeral** disk, so the database can be lost when the pod is recreated. Prefer Option A or B above.

---

## 3.6 Environment variables on RunPod

Set in the pod’s environment or startup script:

**Database (choose one):**

- **SQLite on volume:** `DATABASE_URL=sqlite:////data/labeling.db` (see 3.5 Option A)
- **PostgreSQL:** `DATABASE_URL=postgresql://user:password@db-host:5432/dbname`

**Paths (optional):**

```text
RAW_ROOT_DIR=/data/raw_products
OUTPUT_ROOT_DIR=/data/labels_output
LOCK_MINUTES=30
```

Point these to your mounted volume (e.g. `/data`).

**Model/config (optional):**

```text
PS_DEVICE=cuda
PS_DTYPE=bfloat16
PS_SIMILARITY_THRESHOLD=0.7
```

## 3.7 Install dependencies in the pod

```bash
cd /workspace/ClearCartAI   # or your repo path

python -m venv venv
source venv/bin/activate

pip install wheel setuptools>=61.0
pip uninstall -y torch torchvision torchaudio 2>/dev/null || true
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
pip install --no-build-isolation "git+https://github.com/facebookresearch/sam2.git"
```

First run will download SAM2 and DINOv2 (~10 GB). Optional pre-warm:

```bash
python tests/test_setup.py
```

## 3.8 Start the Gradio UI on RunPod

```bash
cd /workspace/ClearCartAI
source venv/bin/activate
python tools/label_ui_gradio.py
```

- Expose **port 7860** in the RunPod pod settings.  
- Use the RunPod HTTP URL for the app in your browser.

## 3.9 Accessing the UI from anywhere

Once the app is running and port **7860** is exposed in the RunPod dashboard, you can open the UI from **any device or location** (phone, another PC, different network). No VPN is required.

1. Start the pod and run `python tools/label_ui_gradio.py` (the app binds to `0.0.0.0:7860`).
2. In the RunPod dashboard, **expose port 7860** (via “Connect”, “HTTP Service”, or port-forwarding for that port).
3. RunPod will show a **public URL**, e.g. `https://<pod-id>-7860.proxy.runpod.net` or similar.
4. Open that URL in any browser, from anywhere.

**Security:** The Gradio UI has no built-in authentication. Anyone with the URL can use it. For sensitive data, prefer RunPod’s **HTTPS** URLs when available, and consider putting the app behind a reverse proxy with auth or using a VPN if you need access control.

## 3.10 Optional: pipeline scripts on the same pod

```bash
python scripts/run_interactive.py --image-dir ./path/to/images --output ./outputs
python scripts/run_batch.py --image-dir ./path/to/images --reference img_001.jpg --point 250 300 --output ./outputs
```

## 3.11 RunPod checklist

- [ ] GPU ≥ 16 GB VRAM, RAM ≥ 16 GB, Disk ≥ 30–50 GB  
- [ ] **Database:** `DATABASE_URL` set (e.g. `sqlite:////data/labeling.db` on volume, or PostgreSQL URL)  
- [ ] **Volume** mounted (e.g. at `/data`) for DB and for `RAW_ROOT_DIR` / `OUTPUT_ROOT_DIR`  
- [ ] Dependencies installed (requirements, PyTorch CUDA, SAM2)  
- [ ] `python tools/label_ui_gradio.py` running, port **7860** exposed  

---

# Quick reference

| Goal                    | Where        | Main command / step |
|-------------------------|-------------|----------------------|
| Run pipeline once       | Local       | `python scripts/run_interactive.py --image-dir ... --output ...` |
| Run labeling UI         | Local       | Set `DATABASE_URL`, then `python tools/label_ui_gradio.py` → http://localhost:7860 |
| **Public URL (share UI)** | Local     | `pip install pyngrok`, set `NGROK_AUTHTOKEN`, then `python tools/label_ui_gradio.py --public` → use the printed ngrok URL |
| Deploy UI as service    | Local       | Run Postgres + same command; use a process manager or Docker for Postgres |
| Deploy UI in cloud GPU  | RunPod      | Run same Gradio command in pod; expose port 7860; set `DATABASE_URL` and paths |

For more on architecture and config, see **README.md** and **ean_system/config.py** (and **docs/RUNPOD.md** for a RunPod-only reference).
