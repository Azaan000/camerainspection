"""Camera calibration tool computing pixel_size_mm from checkerboard or fiducial marks."""

from __future__ import annotations

import argparse
import math
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np

from camerainspection.core.logging import get_logger
from camerainspection.vision.calibration.manager import (
    RESOLUTION_TARGETS,
    CalibrationManager,
    CalibrationRecord,
)

logger = get_logger("tools.calibrate_camera")


def compute_pixel_size_from_checkerboard(
    image: np.ndarray,
    inner_corners: tuple[int, int] = (7, 5),
    square_size_mm: float = 10.0,
) -> float:
    """Compute mm/px from checkerboard corner detection.

    Args:
        image: BGR or Grayscale input image.
        inner_corners: (cols, rows) inner corner grid size.
        square_size_mm: physical width/height of one square in millimetres.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    ret, corners = cv2.findChessboardCorners(gray, inner_corners, None)
    if not ret or corners is None:
        transposed = (inner_corners[1], inner_corners[0])
        ret, corners = cv2.findChessboardCorners(gray, transposed, None)
        if ret and corners is not None:
            inner_corners = transposed
        else:
            raise ValueError(
                f"Could not find checkerboard corners {inner_corners} in image. "
                "Ensure target is well-lit, in focus, and within field-of-view."
            )

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    corners_subpix = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
    pts = corners_subpix.reshape(-1, 2)

    cols, rows = inner_corners
    h_dists: list[float] = []
    for r in range(rows):
        for c in range(cols - 1):
            idx1 = r * cols + c
            idx2 = r * cols + (c + 1)
            dist_px = float(np.linalg.norm(pts[idx2] - pts[idx1]))
            if dist_px > 0:
                h_dists.append(dist_px)

    if not h_dists:
        raise ValueError("Insufficient corner pairs detected.")

    avg_square_px = float(np.mean(h_dists))
    pixel_size_mm = square_size_mm / avg_square_px
    logger.info(
        f"Checkerboard calibration: average square = {avg_square_px:.2f}px -> "
        f"{pixel_size_mm:.4f} mm/px (square size: {square_size_mm}mm)"
    )
    return pixel_size_mm


def compute_pixel_size_from_two_marks(
    image: np.ndarray,
    known_distance_mm: float = 20.0,
) -> float:
    """Compute mm/px from two dark circular marks on light background."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid_centroids: list[tuple[float, float]] = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 10:
            m = cv2.moments(cnt)
            if m["m00"] > 0:
                cx = m["m10"] / m["m00"]
                cy = m["m01"] / m["m00"]
                valid_centroids.append((cx, cy))

    if len(valid_centroids) < 2:
        raise ValueError(
            f"Expected at least 2 target marks; found {len(valid_centroids)}. "
            "Check thresholding and lighting."
        )

    # Pick the two largest or leftmost/rightmost marks
    valid_centroids.sort(key=lambda pt: pt[0])
    p1 = valid_centroids[0]
    p2 = valid_centroids[-1]
    dist_px = math.hypot(p2[0] - p1[0], p2[1] - p1[1])

    if dist_px <= 0:
        raise ValueError("Measured target mark distance is zero.")

    pixel_size_mm = known_distance_mm / dist_px
    logger.info(
        f"Two-mark calibration: distance = {dist_px:.2f}px -> {pixel_size_mm:.4f} mm/px "
        f"(physical distance: {known_distance_mm}mm)"
    )
    return pixel_size_mm


def calibrate_from_image(
    image: np.ndarray | Path | str,
    camera_name: str,
    target_dimension_mm: float,
    pattern_type: str = "checkerboard",
    operator_id: str = "OPERATOR_1",
    category: str = "generic",
    calibrations_dir: Path | str = "configs/calibrations",
    inner_corners: tuple[int, int] = (7, 5),
) -> CalibrationRecord:
    """Execute end-to-end calibration and persist record."""
    if isinstance(image, (str, Path)):
        img_path = str(image)
        img_arr = cv2.imread(img_path)
        if img_arr is None:
            raise FileNotFoundError(f"Calibration image not found at {img_path}")
    else:
        img_path = "<in_memory_array>"
        img_arr = image

    if pattern_type == "checkerboard":
        pixel_size_mm = compute_pixel_size_from_checkerboard(
            img_arr, inner_corners=inner_corners, square_size_mm=target_dimension_mm
        )
    elif pattern_type in ("two_marks", "fiducials", "dots"):
        pixel_size_mm = compute_pixel_size_from_two_marks(
            img_arr, known_distance_mm=target_dimension_mm
        )
    else:
        raise ValueError(f"Unknown calibration pattern_type '{pattern_type}'")

    record = CalibrationRecord(
        camera_name=camera_name,
        pixel_size_mm=round(pixel_size_mm, 5),
        calibrated_at=datetime.now(UTC),
        operator_id=operator_id,
        image_path=img_path,
        pattern_type=pattern_type,
        target_dimension_mm=target_dimension_mm,
        category=category,
    )

    mgr = CalibrationManager(calibrations_dir=calibrations_dir)
    mgr.save_calibration(record)

    # Check target resolution range
    if category in RESOLUTION_TARGETS:
        low, high = RESOLUTION_TARGETS[category]
        if not (low <= pixel_size_mm <= high):
            logger.warning(
                f"WARNING: Calibrated pixel size {pixel_size_mm:.4f} mm/px is outside "
                f"recommended {category} target range [{low:.3f}, {high:.3f}] mm/px."
            )

    return record


def main() -> None:
    parser = argparse.ArgumentParser(description="Industrial Camera Calibration Tool")
    parser.add_argument("--image", required=True, help="Path to calibration target image")
    parser.add_argument("--camera", required=True, help="Camera identifier / view name")
    parser.add_argument(
        "--target-dimension-mm",
        type=float,
        required=True,
        help="Checkerboard square width or mark distance in mm",
    )
    parser.add_argument(
        "--pattern",
        choices=["checkerboard", "two_marks"],
        default="checkerboard",
        help="Calibration target pattern type",
    )
    parser.add_argument("--operator", default="OPERATOR_1", help="Inspector / technician ID")
    parser.add_argument(
        "--category",
        choices=["stitch", "leather", "plastic", "mechanism", "generic"],
        default="generic",
        help="Station camera category for resolution target validation",
    )
    parser.add_argument("--outdir", default="configs/calibrations", help="Output directory for JSON")
    args = parser.parse_args()

    rec = calibrate_from_image(
        image=Path(args.image),
        camera_name=args.camera,
        target_dimension_mm=args.target_dimension_mm,
        pattern_type=args.pattern,
        operator_id=args.operator,
        category=args.category,
        calibrations_dir=Path(args.outdir),
    )
    print(f"[SUCCESS] Calibrated '{rec.camera_name}': {rec.pixel_size_mm:.5f} mm/px")


if __name__ == "__main__":
    main()
