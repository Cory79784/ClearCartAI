from pathlib import Path

from app.ml_bridge import SegmentationAdapter


class InferenceService:
    def __init__(self) -> None:
        self.adapter = SegmentationAdapter()

    def run(self, input_dir: str, output_dir: str) -> dict:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return self.adapter.run_segmentation(Path(input_dir), Path(output_dir))
