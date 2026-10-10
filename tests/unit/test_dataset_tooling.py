"""Unit tests for dataset tooling, partitioning, and hand-safety augmentation."""

import json
from pathlib import Path

import numpy as np
import pytest

from camerainspection.data.augment import HandSafetyViolationError, SafeImageAugmentor
from camerainspection.data.checklist import DataCollectionAuditor
from camerainspection.data.dataset import DatasetPartitioner
from camerainspection.data.export import BoundingBoxAnnotation, DatasetExporter


def test_split_by_seat_no_leakage() -> None:
    # 100 unique seat IDs
    seats = [f"SEAT-{i:03d}" for i in range(100)]
    train, val, test = DatasetPartitioner.split_by_seat(
        seats, train_ratio=0.70, val_ratio=0.15, test_ratio=0.15, seed=42
    )

    # Check set disjunction (Zero seat overlap)
    set_train = set(train)
    set_val = set(val)
    set_test = set(test)

    assert len(set_train.intersection(set_val)) == 0
    assert len(set_train.intersection(set_test)) == 0
    assert len(set_val.intersection(set_test)) == 0
    assert len(set_train) + len(set_val) + len(set_test) == 100


def test_hand_safety_guard_blocks_flip() -> None:
    augmentor = SafeImageAugmentor(is_hand_sensitive=True)
    img = np.zeros((100, 100, 3), dtype=np.uint8)

    # Mild transforms are allowed
    mild = augmentor.augment_mild(img, brightness_factor=1.05, shift_x=2, shift_y=-2)
    assert mild.shape == img.shape

    # Horizontal flip on hand-sensitive part MUST raise HandSafetyViolationError
    with pytest.raises(HandSafetyViolationError, match="CRITICAL SAFETY VIOLATION"):
        augmentor.augment_mild(img, flip_horizontal=True)


def test_data_collection_checklist_auditor(tmp_path: Path) -> None:
    var_dir = tmp_path / "FRONT_LH_BLACK"
    golden_dir = var_dir / "golden_images"
    golden_dir.mkdir(parents=True)
    (golden_dir / "master.png").write_text("fake image")

    captures_dir = tmp_path / "captures"
    var_caps = captures_dir / "FRONT_LH_BLACK"
    var_caps.mkdir(parents=True)

    # Only 5 good seats exist -> must fail audit (< 200 requirement)
    for i in range(5):
        meta_file = var_caps / f"seat_{i}.json"
        meta_file.write_text(json.dumps({"seat_id": f"s_{i}", "notes": "normal good seat"}))

    audit = DataCollectionAuditor.audit_variant_collection(
        variant_dir=var_dir,
        variant_id="FRONT_LH_BLACK",
        captures_dir=captures_dir,
    )

    assert audit.meets_target is False
    assert any("Insufficient good seats" in msg for msg in audit.missing_requirements)


def test_yolo_and_coco_export(tmp_path: Path) -> None:
    annotations = [
        BoundingBoxAnnotation(
            image_name="seat_01.png",
            class_name="crack",
            class_id=0,
            x_min=50,
            y_min=60,
            width=20,
            height=30,
        )
    ]
    classes = ["crack", "short_shot"]

    # Export YOLO
    yolo_dir = tmp_path / "yolo"
    DatasetExporter.export_yolo(
        image_dir=tmp_path,
        annotations=annotations,
        output_dir=yolo_dir,
        image_width=640,
        image_height=480,
        classes=classes,
    )
    assert (yolo_dir / "labels" / "seat_01.txt").exists()
    assert (yolo_dir / "data.yaml").exists()

    # Export COCO
    coco_json = tmp_path / "coco.json"
    DatasetExporter.export_coco(
        annotations=annotations,
        output_json=coco_json,
        image_width=640,
        image_height=480,
        classes=classes,
    )
    assert coco_json.exists()
    data = json.loads(coco_json.read_text())
    assert len(data["annotations"]) == 1
    assert data["annotations"][0]["bbox"] == [50, 60, 20, 30]
