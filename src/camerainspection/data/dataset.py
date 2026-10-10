"""Dataset partitioning ensuring zero data leakage across train/val/test splits."""

from __future__ import annotations

import json
import random
from pathlib import Path

from pydantic import BaseModel, Field

from camerainspection.core.logging import get_logger

logger = get_logger("data.dataset")


class DatasetSplitRecord(BaseModel):
    train_seats: list[str] = Field(default_factory=list)
    val_seats: list[str] = Field(default_factory=list)
    frozen_test_seats: list[str] = Field(default_factory=list)
    variant_id: str = ""
    created_at: str = ""


class DatasetPartitioner:
    """Partitions datasets strictly by seat ID or lot ID (NEVER by individual image)."""

    @classmethod
    def split_by_seat(
        cls,
        seat_ids: list[str],
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        seed: int = 42,
    ) -> tuple[list[str], list[str], list[str]]:
        """Split unique seat IDs into train, validation, and frozen test groups."""
        if not abs((train_ratio + val_ratio + test_ratio) - 1.0) < 1e-5:
            raise ValueError("Split ratios must sum to 1.0")

        unique_seats = sorted(set(seat_ids))
        if not unique_seats:
            return [], [], []

        rng = random.Random(seed)
        shuffled = list(unique_seats)
        rng.shuffle(shuffled)

        n = len(shuffled)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)

        train = sorted(shuffled[:n_train])
        val = sorted(shuffled[n_train : n_train + n_val])
        frozen_test = sorted(shuffled[n_train + n_val :])

        # If rounding left test empty and we had enough samples, allocate at least 1 to test
        if not frozen_test and len(shuffled) >= 3:
            frozen_test.append(train.pop())

        logger.info(
            f"Dataset split by seat: {len(train)} train, {len(val)} val, {len(frozen_test)} frozen test"
        )
        return train, val, frozen_test

    @classmethod
    def save_split_manifest(
        cls,
        output_file: Path,
        train_seats: list[str],
        val_seats: list[str],
        frozen_test_seats: list[str],
        variant_id: str,
    ) -> None:
        """Persist frozen split manifest to disk for reproducibility."""
        record = DatasetSplitRecord(
            train_seats=train_seats,
            val_seats=val_seats,
            frozen_test_seats=frozen_test_seats,
            variant_id=variant_id,
        )
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(record.model_dump_json(indent=2))

    @classmethod
    def load_split_manifest(cls, manifest_file: Path) -> DatasetSplitRecord:
        """Load frozen split manifest from disk."""
        with open(manifest_file, encoding="utf-8") as f:
            data = json.load(f)
        return DatasetSplitRecord.model_validate(data)
