"""
Central configuration for the Product Segmentation Pipeline.
Override any value via environment variables prefixed with PS_
e.g., PS_SIMILARITY_THRESHOLD=0.7
"""

import os
from pathlib import Path


# ─── Paths (package lives in ean_system/; PROJECT_ROOT = repo root) ───
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHECKPOINT_DIR = PROJECT_ROOT / "models" / "checkpoints"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

# ─── SAM2 Configuration ──────────────────────────────────────
SAM2_CHECKPOINT = os.getenv("PS_SAM2_CHECKPOINT", "sam2.1_hiera_large.pt")
SAM2_CONFIG = os.getenv("PS_SAM2_CONFIG", "configs/sam2.1/sam2.1_hiera_l.yaml")
SAM2_HF_MODEL_ID = "facebook/sam2.1-hiera-large"

# Auto mask generator settings (for generating candidate proposals)
SAM2_POINTS_PER_SIDE = int(os.getenv("PS_POINTS_PER_SIDE", "32"))
SAM2_PRED_IOU_THRESH = float(os.getenv("PS_PRED_IOU_THRESH", "0.86"))
SAM2_STABILITY_SCORE_THRESH = float(os.getenv("PS_STABILITY_SCORE_THRESH", "0.92"))
SAM2_CROP_N_LAYERS = int(os.getenv("PS_CROP_N_LAYERS", "1"))
SAM2_MIN_MASK_REGION_AREA = int(os.getenv("PS_MIN_MASK_REGION_AREA", "100"))

# ─── DINOv2 Configuration ────────────────────────────────────
DINOV2_MODEL_NAME = os.getenv("PS_DINOV2_MODEL", "facebook/dinov2-large")
DINOV2_PATCH_SIZE = 14  # ViT-L/14
DINOV2_EMBEDDING_DIM = 1024  # ViT-L output dim

# ─── Matching Configuration ──────────────────────────────────
SIMILARITY_THRESHOLD = float(os.getenv("PS_SIMILARITY_THRESHOLD", "0.65"))
TOP_K_MATCHES = int(os.getenv("PS_TOP_K_MATCHES", "3"))
NMS_IOU_THRESHOLD = float(os.getenv("PS_NMS_IOU_THRESHOLD", "0.5"))

# Mask area filters (fraction of total image area)
MIN_MASK_AREA_RATIO = float(os.getenv("PS_MIN_MASK_AREA_RATIO", "0.001"))
MAX_MASK_AREA_RATIO = float(os.getenv("PS_MAX_MASK_AREA_RATIO", "0.5"))

# ─── Device Configuration ────────────────────────────────────
DEVICE = os.getenv("PS_DEVICE", "auto")
DTYPE = os.getenv("PS_DTYPE", "bfloat16")  # bfloat16, float16, or float32

# ─── UI Configuration ────────────────────────────────────────
INTERACTIVE_FIGSIZE = (12, 8)
GALLERY_COLS = 4
MASK_ALPHA = 0.45
MASK_COLOR = (0.2, 0.8, 0.2)  # Green overlay

# ─── Export Configuration ─────────────────────────────────────
EXPORT_CUTOUT_BG = (0, 0, 0, 0)  # Transparent background
EXPORT_MASK_FORMAT = "png"
EXPORT_VISUALIZATION = True


def get_device():
    """Resolve the actual torch device."""
    import torch
    if DEVICE == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")
    return torch.device(DEVICE)


def get_dtype():
    """Resolve the torch dtype."""
    import torch
    device = get_device()
    # CPU execution is most stable with float32.
    if device.type == "cpu":
        return torch.float32
    dtype_map = {
        "bfloat16": torch.bfloat16,
        "float16": torch.float16,
        "float32": torch.float32,
    }
    return dtype_map.get(DTYPE, torch.bfloat16)


def print_config():
    """Print current configuration for debugging."""
    print("=" * 60)
    print("Product Segmentation Pipeline Configuration")
    print("=" * 60)
    print(f"  Device:              {get_device()}")
    print(f"  DType:               {DTYPE}")
    print(f"  SAM2 Checkpoint:     {SAM2_CHECKPOINT}")
    print(f"  DINOv2 Model:        {DINOV2_MODEL_NAME}")
    print(f"  Similarity Thresh:   {SIMILARITY_THRESHOLD}")
    print(f"  Top-K Matches:       {TOP_K_MATCHES}")
    print(f"  NMS IoU Threshold:   {NMS_IOU_THRESHOLD}")
    print(f"  Mask Area Range:     [{MIN_MASK_AREA_RATIO}, {MAX_MASK_AREA_RATIO}]")
    print("=" * 60)
