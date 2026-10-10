"""Synthetic test fixtures for Station 2 stitch inspection."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def make_stitch_seam(
    width: int = 640,
    height: int = 200,
    n_stitches: int = 30,
    pitch_px: int = 18,
    thread_color_bgr: tuple[int, int, int] = (210, 210, 210),
    stitch_w: int = 10,
    stitch_h: int = 6,
    seam_y: int | None = None,
    skip_index: int | None = None,
    add_loose_end: bool = False,
    add_broken_thread: bool = False,
    shift_y_at_half: int = 0,
) -> np.ndarray:
    """Render a synthetic stitch seam on dark leather background for deterministic testing.

    Args:
        skip_index:  If set, omits stitch at that index to create a skipped stitch gap.
        add_loose_end: Adds a dangling thread tail of ~15px at end.
        add_broken_thread: Paints a dark gap gap through stitch at index 5.
        shift_y_at_half: Shift seam Y in second half by this many pixels (double seam simulation).
    """
    canvas = np.full((height, width, 3), 28, dtype=np.uint8)  # Dark leather base
    sy = seam_y if seam_y is not None else height // 2

    start_x = 30
    for i in range(n_stitches):
        if skip_index is not None and i == skip_index:
            continue  # Leave gap (skip)

        x = start_x + i * pitch_px
        y = sy if i < (n_stitches // 2) else (sy + shift_y_at_half)

        if x + stitch_w > width:
            break

        # Draw the stitch dot/dash on dark background
        cv2.rectangle(
            canvas,
            (x, y - stitch_h // 2),
            (x + stitch_w, y + stitch_h // 2),
            thread_color_bgr,
            -1,
        )

        # Broken thread: paint a black gap through stitch
        if add_broken_thread and i == 5:
            cx = x + stitch_w // 2
            canvas[y - stitch_h // 2 : y + stitch_h // 2, cx - 1 : cx + 1] = (10, 10, 10)

    # Loose end: paint a dangling thread tail from last stitch
    if add_loose_end:
        last_x = start_x + (n_stitches - 1) * pitch_px + stitch_w
        cv2.line(canvas, (last_x, sy), (last_x + 15, sy + 8), thread_color_bgr, 2)

    return canvas


def generate_station2_replay_frames(output_dir: Path) -> None:
    """Create replay image set for Station 2 integration tests matching station_2_stitch config."""
    output_dir.mkdir(parents=True, exist_ok=True)
    w, h = 2592, 1944
    pitch_px = int(round(25.4 / 6.0 / 0.05))  # 85 px for 6.0 SPI at 0.05 mm/px
    seam_y = 500  # Centered in main_seam ROI (y: 300..700)
    stitch_w = 40
    stitch_h = 10
    n = 25

    def _base(**extra) -> np.ndarray:  # type: ignore[no-untyped-def]
        return make_stitch_seam(
            width=w, height=h, n_stitches=n, pitch_px=pitch_px,
            stitch_w=stitch_w, stitch_h=stitch_h, seam_y=seam_y,
            **extra,
        )

    # 1. Normal good seam
    cv2.imwrite(str(output_dir / "01_pass_normal.png"), _base())

    # 2. Skipped stitch at position 10 (gap = 85px * 0.05mm = 4.25mm -> in (0, 5) review band)
    cv2.imwrite(str(output_dir / "02_review_skip.png"), _base(skip_index=10))

    # 3. Broken thread
    cv2.imwrite(str(output_dir / "03_fail_broken_thread.png"), _base(add_broken_thread=True))

    # 4. Loose end dangling
    cv2.imwrite(str(output_dir / "04_review_loose_end.png"), _base(add_loose_end=True))

    # 5. Wrong thread color (red thread on leather - large Delta E)
    cv2.imwrite(str(output_dir / "05_fail_wrong_color.png"), _base(thread_color_bgr=(30, 30, 200)))

