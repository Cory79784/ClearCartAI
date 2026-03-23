from pathlib import Path
from typing import Any
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ean_system.pipeline import ProductSegmentationPipeline
from ean_system.image_utils import load_images_from_directory


class SegmentationAdapter:
    def __init__(self) -> None:
        self.pipeline = ProductSegmentationPipeline()

    def run_segmentation(self, input_dir: Path, output_dir: Path) -> dict[str, Any]:
        images = load_images_from_directory(str(input_dir))
        image_paths = [p for p, _ in images]
        if len(image_paths) < 1:
            raise ValueError("No images found for inference")
        reference_path = image_paths[0]
        # Minimal wrapper: keep pipeline behavior and pick image center as point.
        ref_img = images[0][1]
        point = (ref_img.shape[1] // 2, ref_img.shape[0] // 2)
        result = self.pipeline.run_with_point(
            image_paths=image_paths,
            reference_image_path=reference_path,
            reference_point=point,
            output_dir=str(output_dir),
        )
        return {
            "status": "completed",
            "reference_image_path": reference_path,
            "total_matches": result.total_matches,
            "total_images": result.total_images,
            "output_dir": str(output_dir),
            "artifacts": {
                "summary_json": str(output_dir / "summary.json"),
                "gallery": str(output_dir / "gallery.jpg"),
                "masks_dir": str(output_dir / "masks"),
                "overlays_dir": str(output_dir / "overlays"),
                "cutouts_dir": str(output_dir / "cutouts"),
            },
        }
