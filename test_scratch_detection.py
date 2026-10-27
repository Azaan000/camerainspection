#!/usr/bin/env python3
"""Quick test to verify scratch detection improvement."""

import cv2
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from camerainspection.vision.station1.surface_analysis import SurfaceAnalyzer

def test_scratch_image(image_path: str):
    """Test scratch detection on a single image."""
    print(f"\n{'='*60}")
    print(f"Testing: {image_path}")
    print(f"{'='*60}")

    img = cv2.imread(image_path)
    if img is None:
        print(f"ERROR: Could not load image: {image_path}")
        return

    print(f"Image shape: {img.shape}")

    # Test with relaxed=False (old behavior)
    analyzer = SurfaceAnalyzer(
        anomaly_threshold=0.45,
        blur_ksize=101,
        diff_threshold=25,
        min_contrast=25.0,
    )

    print("\n--- Standard thresholds (relaxed=False) ---")
    regions_standard = analyzer.analyze(img, pixel_size_mm=0.18, relaxed=False)
    print(f"Found {len(regions_standard)} regions")
    for i, r in enumerate(regions_standard, 1):
        print(f"  {i}. {r.defect_type.value}: bbox={r.bbox_px}, aspect={r.aspect_ratio:.2f}, score={r.anomaly_score:.3f}")

    print("\n--- Relaxed thresholds (relaxed=True) ---")
    regions_relaxed = analyzer.analyze(img, pixel_size_mm=0.18, relaxed=True)
    print(f"Found {len(regions_relaxed)} regions")
    for i, r in enumerate(regions_relaxed, 1):
        print(f"  {i}. {r.defect_type.value}: bbox={r.bbox_px}, aspect={r.aspect_ratio:.2f}, score={r.anomaly_score:.3f}")

    # Draw results
    annotated = img.copy()
    for r in regions_relaxed:
        x, y, w, h = r.bbox_px
        color = (0, 255, 0) if r.defect_type.value == "scratch" else (0, 0, 255)
        cv2.rectangle(annotated, (x, y), (x+w, y+h), color, 2)
        label = f"{r.defect_type.value} {r.aspect_ratio:.1f}"
        cv2.putText(annotated, label, (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    # Save result
    out_path = image_path.replace(".jpg", "_analyzed.jpg")
    cv2.imwrite(out_path, annotated)
    print(f"\nSaved annotated result to: {out_path}")

if __name__ == "__main__":
    # Test the injected scratch images
    test_images = [
        "storage/captures/INJECTED/STATION_1_main_1793110320.jpg",
        "storage/captures/INJECTED/STATION_1_main_1793110341.jpg",
        "storage/captures/INJECTED/STATION_1_main_1793110413.jpg",
    ]

    for img_path in test_images:
        if Path(img_path).exists():
            test_scratch_image(img_path)
        else:
            print(f"Skipping missing file: {img_path}")
