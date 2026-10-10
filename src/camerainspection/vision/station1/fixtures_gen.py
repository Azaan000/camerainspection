"""Synthetic leather / rexene image generator for Station 1 deterministic testing."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def _dark_leather_base(
    width: int = 640,
    height: int = 480,
    base_gray: int = 35,
    grain_strength: int = 8,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Generate a dark leather-like BGR canvas with subtle grain texture."""
    if rng is None:
        rng = np.random.default_rng(42)
    # Grain = Gaussian noise blurred slightly to simulate material texture
    noise = rng.integers(-grain_strength, grain_strength + 1, (height, width), dtype=np.int16)
    noise_blurred = cv2.GaussianBlur(noise.astype(np.float32), (5, 5), 0)
    gray = np.clip(base_gray + noise_blurred, 0, 255).astype(np.uint8)
    canvas = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    return canvas


def make_clean_leather(width: int = 640, height: int = 480) -> np.ndarray:
    """Return a defect-free dark leather panel."""
    return _dark_leather_base(width, height)


def make_leather_with_scratch(
    width: int = 640,
    height: int = 480,
    x0: int = 100,
    y0: int = 240,
    length_px: int = 80,
    thickness: int = 2,
    brightness_add: int = 60,
) -> np.ndarray:
    """Bright horizontal scratch line (simulates thread-drag or fingernail mark)."""
    canvas = _dark_leather_base(width, height)
    x1 = x0 + length_px
    cv2.line(canvas, (x0, y0), (x1, y0), (brightness_add, brightness_add, brightness_add), thickness)
    return canvas


def make_leather_with_cut(
    width: int = 640,
    height: int = 480,
    x0: int = 200,
    y0: int = 200,
    length_px: int = 60,
    thickness: int = 3,
) -> np.ndarray:
    """Dark diagonal cut / score mark (material surface broken)."""
    canvas = _dark_leather_base(width, height)
    x1, y1 = x0 + length_px, y0 + length_px // 4
    cv2.line(canvas, (x0, y0), (x1, y1), (0, 0, 0), thickness)
    return canvas


def make_leather_with_pinhole(
    width: int = 640,
    height: int = 480,
    cx: int = 300,
    cy: int = 240,
    radius: int = 3,
) -> np.ndarray:
    """Tiny dark circle (pinhole = needle penetration through material)."""
    canvas = _dark_leather_base(width, height)
    cv2.circle(canvas, (cx, cy), radius, (0, 0, 0), -1)
    return canvas


def make_leather_with_stain(
    width: int = 640,
    height: int = 480,
    cx: int = 320,
    cy: int = 240,
    rx: int = 30,
    ry: int = 20,
    darkness: int = 35,
) -> np.ndarray:
    """Dark elliptical stain with high local contrast."""
    canvas = _dark_leather_base(width, height)
    cv2.ellipse(canvas, (cx, cy), (rx, ry), 0, 0, 360, (0, 0, 0), -1)
    return canvas


def make_leather_with_shade_band(
    width: int = 640,
    height: int = 480,
    band_start_x: int = 100,
    band_width: int = 350,
    shade_delta: int = 50,
) -> np.ndarray:
    """Horizontal shade / colour band — strong enough to clear the diff threshold."""
    canvas = _dark_leather_base(width, height)
    # Apply a flat luminance increase across the entire band (not a ramp) so
    # the Gaussian background subtraction sees the sharp boundary at band edges
    canvas[:, band_start_x : band_start_x + band_width] = np.clip(
        canvas[:, band_start_x : band_start_x + band_width].astype(np.int32) + shade_delta,
        0, 255,
    ).astype(np.uint8)
    return canvas




def make_leather_with_coating_streak(
    width: int = 640,
    height: int = 480,
    x0: int = 50,
    y0: int = 180,
    length_px: int = 200,
    thickness: int = 4,
    brightness_add: int = 70,
) -> np.ndarray:
    """Long bright coating-agent streak (wider and longer than a scratch)."""
    canvas = _dark_leather_base(width, height)
    x1 = x0 + length_px
    # Slightly wavy: add small y offset at midpoint
    pts = np.array([[x0, y0], [x0 + length_px // 2, y0 - 3], [x1, y0 + 2]], np.int32)
    cv2.polylines(
        canvas, [pts], False,
        (brightness_add, brightness_add, brightness_add), thickness
    )
    return canvas


def generate_station1_replay_frames(output_dir: Path) -> None:
    """Write replay PNG frames for Station 1 integration tests.

    Uses 2400×1700 canvas so all station ROIs (seating_face: x200,y200,w2200,h1500 and
    side_back: x100,y100,w2400,h1800) fit without being clipped.
    Defects are injected inside the seating_face zone so the most restrictive
    zone limits (pass_max=0 for scratch, fail_on_any for cut/pinhole) fire correctly.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    w, h = 2400, 1700
    # seating_face zone: x200..2400, y200..1700 - inject defects well inside it
    sf_x, sf_y = 400, 500   # injection origin inside seating_face

    # Frame 1: clean
    cv2.imwrite(str(output_dir / "01_pass_clean.png"), make_clean_leather(w, h))

    # Frame 2: scratch at 80px inside seating_face (80 * 0.08mm = 6.4mm → FAIL > fail_at=2mm)
    cv2.imwrite(
        str(output_dir / "02_fail_scratch.png"),
        make_leather_with_scratch(w, h, x0=sf_x, y0=sf_y, length_px=80, brightness_add=60),
    )

    # Frame 3: cut inside seating_face
    cv2.imwrite(
        str(output_dir / "03_fail_cut.png"),
        make_leather_with_cut(w, h, x0=sf_x, y0=sf_y, length_px=60, thickness=3),
    )

    # Frame 4: pinhole inside seating_face
    cv2.imwrite(
        str(output_dir / "04_fail_pinhole.png"),
        make_leather_with_pinhole(w, h, cx=sf_x + 100, cy=sf_y, radius=3),
    )

    # Frame 5: stain inside seating_face
    cv2.imwrite(
        str(output_dir / "05_review_stain.png"),
        make_leather_with_stain(w, h, cx=sf_x + 200, cy=sf_y, rx=30, ry=20),
    )

