"""Export utilities for CVAT-compatible COCO and Ultralytics YOLO formats."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from camerainspection.core.logging import get_logger

logger = get_logger("data.export")


class BoundingBoxAnnotation(BaseModel):
    image_name: str
    class_name: str
    class_id: int
    x_min: int
    y_min: int
    width: int
    height: int


class DatasetExporter:
    """Exports datasets with bounding boxes to standard computer vision formats."""

    @classmethod
    def export_yolo(
        cls,
        image_dir: Path,
        annotations: list[BoundingBoxAnnotation],
        output_dir: Path,
        image_width: int,
        image_height: int,
        classes: list[str],
    ) -> None:
        """Export YOLO format: images in /images, normalized .txt in /labels, classes in data.yaml."""
        labels_dir = output_dir / "labels"
        labels_dir.mkdir(parents=True, exist_ok=True)

        # Group annotations by image
        grouped: dict[str, list[BoundingBoxAnnotation]] = {}
        for ann in annotations:
            grouped.setdefault(ann.image_name, []).append(ann)

        for img_name, anns in grouped.items():
            txt_path = labels_dir / f"{Path(img_name).stem}.txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                for ann in anns:
                    # Normalize YOLO coords [class_id, x_center, y_center, width, height]
                    x_c = (ann.x_min + ann.width / 2.0) / image_width
                    y_c = (ann.y_min + ann.height / 2.0) / image_height
                    w_n = ann.width / image_width
                    h_n = ann.height / image_height
                    f.write(f"{ann.class_id} {x_c:.6f} {y_c:.6f} {w_n:.6f} {h_n:.6f}\n")

        # Write data.yaml metadata
        yaml_path = output_dir / "data.yaml"
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(f"nc: {len(classes)}\n")
            f.write(f"names: {classes}\n")

        logger.info(f"Exported YOLO dataset to {output_dir}")

    @classmethod
    def export_coco(
        cls,
        annotations: list[BoundingBoxAnnotation],
        output_json: Path,
        image_width: int,
        image_height: int,
        classes: list[str],
    ) -> None:
        """Export COCO JSON format compatible with CVAT."""
        categories = [{"id": i, "name": name, "supercategory": "defect"} for i, name in enumerate(classes)]
        images: list[dict[str, Any]] = []
        coco_annotations: list[dict[str, Any]] = []

        seen_images: dict[str, int] = {}
        ann_id = 1

        for ann in annotations:
            if ann.image_name not in seen_images:
                img_id = len(seen_images) + 1
                seen_images[ann.image_name] = img_id
                images.append({
                    "id": img_id,
                    "file_name": ann.image_name,
                    "width": image_width,
                    "height": image_height,
                })
            else:
                img_id = seen_images[ann.image_name]

            coco_annotations.append({
                "id": ann_id,
                "image_id": img_id,
                "category_id": ann.class_id,
                "bbox": [ann.x_min, ann.y_min, ann.width, ann.height],
                "area": float(ann.width * ann.height),
                "iscrowd": 0,
            })
            ann_id += 1

        coco_payload = {
            "images": images,
            "annotations": coco_annotations,
            "categories": categories,
        }

        output_json.parent.mkdir(parents=True, exist_ok=True)
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(coco_payload, f, indent=2)

        logger.info(f"Exported COCO JSON to {output_json}")
