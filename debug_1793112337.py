#!/usr/bin/env python3
"""Debug why INJECT_1793112337 returns LEATHER_ANOMALY instead of scratch."""

import cv2
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from camerainspection.vision.station1.surface_analysis import SurfaceAnalyzer

def debug_image(image_path: str):
    print(f"\n{'='*70}")
    print(f"Debugging: {image_path}")
    print(f"{'='*70}")

    img = cv2.imread(image_path)
    if img is None:
        print(f"ERROR: Could not load {image_path}")
        return

    h, w = img.shape[:2]
    print(f"Full image: {w}x{h}")

    # The red box in the image appears to be roughly at: x~310, y~130, w~140, h~240
    # Let me extract that region
    bbox_x, bbox_y, bbox_w, bbox_h = 310, 130, 140, 240
    roi = img[bbox_y:bbox_y+bbox_h, bbox_x:bbox_x+bbox_w]

    print(f"\nROI crop (simulating PatchCore bbox): {bbox_w}x{bbox_h}")

    # Save the ROI for inspection
    cv2.imwrite("debug_roi.jpg", roi)
    print(f"Saved ROI to: debug_roi.jpg")

    # Test with standard analyzer
    analyzer = SurfaceAnalyzer(
        anomaly_threshold=0.4,
        blur_ksize=101,
        diff_threshold=25,
        min_contrast=25.0,
    )

    print("\n--- Standard thresholds (relaxed=False) ---")
    regions_std = analyzer.analyze(roi, pixel_size_mm=0.18, relaxed=False)
    print(f"Found {len(regions_std)} regions")
    for i, r in enumerate(regions_std, 1):
        print(f"  {i}. {r.defect_type.value}: bbox={r.bbox_px}, aspect={r.aspect_ratio:.2f}, "
              f"area={r.area_px:.0f}, score={r.anomaly_score:.3f}")

    print("\n--- Relaxed thresholds (relaxed=True) ---")
    regions_rel = analyzer.analyze(roi, pixel_size_mm=0.18, relaxed=True)
    print(f"Found {len(regions_rel)} regions")
    for i, r in enumerate(regions_rel, 1):
        print(f"  {i}. {r.defect_type.value}: bbox={r.bbox_px}, aspect={r.aspect_ratio:.2f}, "
              f"area={r.area_px:.0f}, score={r.anomaly_score:.3f}")

    # Annotate and save
    annotated = roi.copy()
    for r in regions_rel:
        x, y, w, h = r.bbox_px
        color = (0, 255, 0) if r.defect_type.value == "scratch" else (0, 165, 255)
        cv2.rectangle(annotated, (x, y), (x+w, y+h), color, 2)
        label = f"{r.defect_type.value[:8]} {r.aspect_ratio:.1f}"
        cv2.putText(annotated, label, (x, max(y-3, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

    cv2.imwrite("debug_annotated.jpg", annotated)
    print(f"\nSaved annotated ROI to: debug_annotated.jpg")

    # Also test on the FULL image to see what happens
    print("\n" + "="*70)
    print("Testing on FULL image (not just PatchCore ROI):")
    print("="*70)

    print("\n--- Full image, relaxed=True ---")
    regions_full = analyzer.analyze(img, pixel_size_mm=0.18, relaxed=True)
    print(f"Found {len(regions_full)} regions")
    for i, r in enumerate(regions_full[:15], 1):  # Show top 15
        print(f"  {i}. {r.defect_type.value}: bbox={r.bbox_px}, aspect={r.aspect_ratio:.2f}, "
              f"area={r.area_px:.0f}, score={r.anomaly_score:.3f}")

if __name__ == "__main__":
    debug_image("storage/captures/INJECTED/STATION_1_main_1793112337.jpg")
