"""Synthetic test scene generator for Station 4 (Complete Seat & Mechanism)."""

from __future__ import annotations

import math
from pathlib import Path
import cv2
import numpy as np


def generate_station4_test_scene(
    width: int = 2592,
    height: int = 1944,
    recliner_angle_deg: float = 90.0,
    track_end_pos_mm: float = 240.0,
    pixel_size_mm: float = 0.15,
) -> np.ndarray:
    """Render a synthetic complete seat scene matching station_4_complete.yaml ROIs.

    ROIs in station_4_complete.yaml:
      recliner_pivot: x=400, y=800, w=500, h=500
      track_travel:   x=200, y=1400, w=2000, h=400

    Args:
        recliner_angle_deg: Angle of lever arm (90 deg = upright nominal).
        track_end_pos_mm: Linear travel position in mm (240.0 mm nominal).
        pixel_size_mm: 0.15 mm/px.
    """
    canvas = np.full((height, width, 3), 25, dtype=np.uint8)

    # 1. Base seat outline / cushion for context
    cv2.rectangle(canvas, (300, 300), (2200, 1500), (40, 40, 40), -1)

    # 2. Recliner lever in recliner_pivot ROI (x: 400..900, y: 800..1300)
    # Pivot center at (650, 1050)
    pivot_cx, pivot_cy = 650, 1050
    lever_len = 160
    lever_thickness = 24

    # Calculate end point from angle
    rad = math.radians(recliner_angle_deg)
    # Note: 90 deg = straight up (dy < 0)
    end_x = int(round(pivot_cx + lever_len * math.cos(rad)))
    end_y = int(round(pivot_cy - lever_len * math.sin(rad)))

    # Draw lever as rounded thick bar
    cv2.line(canvas, (pivot_cx, pivot_cy), (end_x, end_y), (180, 180, 180), lever_thickness)
    cv2.circle(canvas, (pivot_cx, pivot_cy), 28, (200, 200, 200), -1)
    cv2.circle(canvas, (end_x, end_y), 18, (180, 180, 180), -1)

    # 3. Track travel indicator in track_travel ROI (x: 200..2200, y: 1400..1800)
    # Track datum x = 200 (start of ROI). Travel position in pixels:
    travel_px = int(round(track_end_pos_mm / pixel_size_mm))
    pointer_x = 200 + travel_px
    pointer_y = 1600

    # Draw track rail
    cv2.rectangle(canvas, (200, 1580), (2200, 1620), (50, 50, 50), -1)

    # Draw pointer/marker
    if 200 <= pointer_x <= 2200:
        cv2.rectangle(canvas, (pointer_x - 10, pointer_y - 25), (pointer_x + 10, pointer_y + 25), (220, 220, 220), -1)

    return canvas


def generate_station4_replay_frames(output_dir: Path) -> None:
    """Generate replay test set for Station 4 integration tests."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Frame 1: Nominal pass (90.0 deg, 240.0 mm)
    cv2.imwrite(
        str(output_dir / "01_pass_nominal.png"),
        generate_station4_test_scene(recliner_angle_deg=90.0, track_end_pos_mm=240.0),
    )

    # Frame 2: Recliner angle review/fail (out of spec by 3 degrees: 93.0 deg vs 90 nominal)
    cv2.imwrite(
        str(output_dir / "02_fail_recliner_angle.png"),
        generate_station4_test_scene(recliner_angle_deg=93.0, track_end_pos_mm=240.0),
    )

    # Frame 3: Track end position fail (travel short by 4mm: 236.0 mm vs 240 nominal)
    cv2.imwrite(
        str(output_dir / "03_fail_track_position.png"),
        generate_station4_test_scene(recliner_angle_deg=90.0, track_end_pos_mm=236.0),
    )
