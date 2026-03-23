"""
SAM2 Segmentation Module

Provides two segmentation modes:
1. Interactive: Click-based prompting for reference product selection
2. Automatic: Generate all candidate masks in an image for matching
"""

import numpy as np
import torch
from typing import List, Tuple, Optional, Dict, Any
from contextlib import nullcontext

from . import config
from .model_loader import ModelLoader


def _autocast_or_noop():
    device = config.get_device()
    # CPU autocast with unsupported dtype emits warnings and disables itself.
    if str(device) == "cpu":
        return nullcontext()
    return torch.autocast(str(device), dtype=config.get_dtype())


class SAM2InteractiveSegmenter:
    """Click-to-segment using SAM2 image predictor."""

    def __init__(self):
        self.predictor = ModelLoader.get_sam2_predictor()
        self._current_image = None

    def set_image(self, image: np.ndarray):
        """Set the image for segmentation.

        Args:
            image: RGB numpy array, shape (H, W, 3), dtype uint8
        """
        self._current_image = image
        with torch.inference_mode(), _autocast_or_noop():
            self.predictor.set_image(image)

    def segment_with_points(
        self,
        point_coords: np.ndarray,
        point_labels: np.ndarray,
        multimask_output: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Segment object given point prompts.

        Args:
            point_coords: (N, 2) array of (x, y) coordinates
            point_labels: (N,) array of labels (1=positive, 0=negative)
            multimask_output: If True, return 3 mask candidates

        Returns:
            masks: (K, H, W) boolean masks
            scores: (K,) predicted IoU scores
            logits: (K, 256, 256) low-res mask logits (for refinement)
        """
        with torch.inference_mode(), _autocast_or_noop():
            masks, scores, logits = self.predictor.predict(
                point_coords=point_coords,
                point_labels=point_labels,
                multimask_output=multimask_output,
            )
        return masks, scores, logits

    def segment_with_box(
        self,
        box: np.ndarray,
        multimask_output: bool = False,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Segment object given a bounding box prompt.

        Args:
            box: (4,) array of [x1, y1, x2, y2]

        Returns:
            masks, scores, logits (same as segment_with_points)
        """
        with torch.inference_mode(), _autocast_or_noop():
            masks, scores, logits = self.predictor.predict(
                box=box[None, :],  # (1, 4)
                multimask_output=multimask_output,
            )
        return masks, scores, logits

    def refine_mask(
        self,
        point_coords: np.ndarray,
        point_labels: np.ndarray,
        mask_input: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Refine an existing mask with additional point prompts.

        Args:
            point_coords: Additional points
            point_labels: Additional labels
            mask_input: (1, 256, 256) low-res logits from previous prediction

        Returns:
            Refined masks, scores, logits
        """
        with torch.inference_mode(), _autocast_or_noop():
            masks, scores, logits = self.predictor.predict(
                point_coords=point_coords,
                point_labels=point_labels,
                mask_input=mask_input,
                multimask_output=False,
            )
        return masks, scores, logits


class SAM2AutoSegmenter:
    """Generate all candidate segmentation masks in an image."""

    def __init__(self):
        self.generator = ModelLoader.get_sam2_auto_generator()

    def generate_proposals(
        self,
        image: np.ndarray,
        min_area_ratio: float = None,
        max_area_ratio: float = None,
    ) -> List[Dict[str, Any]]:
        """Generate all segmentation proposals for an image.

        Args:
            image: RGB numpy array, shape (H, W, 3), dtype uint8
            min_area_ratio: Minimum mask area as fraction of image area
            max_area_ratio: Maximum mask area as fraction of image area

        Returns:
            List of proposal dicts, each containing:
                - 'segmentation': (H, W) boolean mask
                - 'bbox': [x, y, w, h] bounding box
                - 'area': number of pixels
                - 'predicted_iou': SAM2's IoU prediction
                - 'stability_score': mask stability score
        """
        if min_area_ratio is None:
            min_area_ratio = config.MIN_MASK_AREA_RATIO
        if max_area_ratio is None:
            max_area_ratio = config.MAX_MASK_AREA_RATIO

        # Generate all masks
        with torch.inference_mode(), _autocast_or_noop():
            raw_masks = self.generator.generate(image)

        # Filter by area
        image_area = image.shape[0] * image.shape[1]
        min_area = min_area_ratio * image_area
        max_area = max_area_ratio * image_area

        proposals = []
        for mask_data in raw_masks:
            area = mask_data['area']
            if area < min_area or area > max_area:
                continue
            proposals.append(mask_data)

        # Sort by predicted IoU (highest first)
        proposals.sort(key=lambda x: x['predicted_iou'], reverse=True)

        print(f"[SAM2Auto] Generated {len(proposals)} proposals "
              f"(filtered from {len(raw_masks)} raw masks)")

        return proposals


def mask_to_bbox(mask: np.ndarray) -> np.ndarray:
    """Convert a boolean mask to a bounding box [x1, y1, x2, y2]."""
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if not rows.any():
        return np.array([0, 0, 0, 0])
    y1, y2 = np.where(rows)[0][[0, -1]]
    x1, x2 = np.where(cols)[0][[0, -1]]
    return np.array([x1, y1, x2 + 1, y2 + 1])


def bbox_iou(box1: np.ndarray, box2: np.ndarray) -> float:
    """Compute IoU between two boxes [x1, y1, x2, y2]."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0
