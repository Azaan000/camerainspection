#!/usr/bin/env python3
"""Direct test of the scratch classification fix without running the full service."""

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "src"))

from camerainspection.vision.station1.surface_analysis import SurfaceAnalyzer, LeatherDefectType
from camerainspection.core.models import BoundingBox


def test_image_with_full_pipeline(image_path: str):
    """Test the complete pipeline: PatchCore detection -> Classical classification."""

    print(f"\n{'='*80}")
    print(f"Testing: {image_path}")
    print(f"{'='*80}\n")

    # Load image
    img = cv2.imread(image_path)
    if img is None:
        print(f"ERROR: Could not load {image_path}")
        return

    h, w = img.shape[:2]
    print(f"Image size: {w}x{h}\n")

    # Step 1: PatchCore detection (simulating what station_1.py does)
    print("Step 1: PatchCore Detection")
    print("-" * 40)

    # We'll simulate PatchCore finding the region around (310, 130, 140, 240)
    # In the real system, this comes from the ONNX model
    patchcore_bbox = BoundingBox(x=310, y=130, w=140, h=240)
    patchcore_score = 1.00

    print(f"PatchCore detected anomaly:")
    print(f"  Bbox: x={patchcore_bbox.x}, y={patchcore_bbox.y}, w={patchcore_bbox.w}, h={patchcore_bbox.h}")
    print(f"  Score: {patchcore_score:.2f}")
    print(f"  Bbox aspect ratio: {max(patchcore_bbox.w, patchcore_bbox.h) / max(min(patchcore_bbox.w, patchcore_bbox.h), 1):.2f}")

    # Step 2: Extract ROI and classify (what station_1.py does)
    print("\nStep 2: Classical Classification on ROI")
    print("-" * 40)

    roi = img[patchcore_bbox.y:patchcore_bbox.y_max,
              patchcore_bbox.x:patchcore_bbox.x_max]

    print(f"ROI size: {roi.shape[1]}x{roi.shape[0]}")

    # Create analyzer
    analyzer = SurfaceAnalyzer(
        anomaly_threshold=0.4,
        blur_ksize=101,
        diff_threshold=25,
        min_contrast=25.0,
    )

    # Analyze with relaxed=True (as station_1.py does for PatchCore detections)
    regions = analyzer.analyze(roi, pixel_size_mm=0.18, relaxed=True)

    print(f"\nClassifier found {len(regions)} regions:")
    for i, r in enumerate(regions, 1):
        print(f"  {i}. {r.defect_type.value}: bbox={r.bbox_px}, aspect={r.aspect_ratio:.2f}, "
              f"area={r.area_px:.0f}, score={r.anomaly_score:.3f}")

    # Step 3: Apply station_1.py logic - filter shade bands and use bbox fallback
    print("\nStep 3: Apply Station 1 Classification Logic")
    print("-" * 40)

    defect_type_name = "LEATHER_ANOMALY"  # default

    if regions:
        # Filter out shade bands
        non_shade_regions = [r for r in regions if r.defect_type != LeatherDefectType.SHADE_BAND]

        if non_shade_regions:
            # Use highest-scoring non-shade region
            primary_region = max(non_shade_regions, key=lambda r: r.anomaly_score)
            defect_type_name = primary_region.defect_type.value
            print(f"[OK] Found non-shade region: {defect_type_name}")
            print(f"  Using region: bbox={primary_region.bbox_px}, aspect={primary_region.aspect_ratio:.2f}")
        else:
            # Only shade bands found - use bbox shape fallback
            print("[!] Only shade bands found - applying bbox-shape fallback")

            bbox_aspect = max(patchcore_bbox.w, patchcore_bbox.h) / max(min(patchcore_bbox.w, patchcore_bbox.h), 1)
            bbox_max_dim = max(patchcore_bbox.w, patchcore_bbox.h)

            print(f"  PatchCore bbox aspect: {bbox_aspect:.2f}")
            print(f"  PatchCore bbox max_dim: {bbox_max_dim}")

            if bbox_aspect >= 1.5 and bbox_max_dim <= 400:
                defect_type_name = "scratch"
                print(f"[OK] Bbox is moderately elongated (aspect >= 1.5, max_dim <= 400) -> SCRATCH")
            else:
                # Not elongated - keep as shade_band or LEATHER_ANOMALY
                primary_region = max(regions, key=lambda r: r.anomaly_score)
                defect_type_name = primary_region.defect_type.value
                print(f"[!] Bbox not elongated -> {defect_type_name}")
    else:
        print("[!] No regions found at all -> LEATHER_ANOMALY")

    # Step 4: Final result
    print("\n" + "="*80)
    print(f"FINAL CLASSIFICATION: leather.{defect_type_name.upper()}")
    print("="*80)

    # Expected vs Actual
    print(f"\n{'Expected:':<15} leather.SCRATCH (visual inspection shows diagonal scratch)")
    print(f"{'Actual:':<15} leather.{defect_type_name.upper()}")

    if defect_type_name.lower() == "scratch":
        print("\n[SUCCESS] Correctly classified as SCRATCH!")
    else:
        print(f"\n[FAILED] Still classified as {defect_type_name.upper()}")

    return defect_type_name


if __name__ == "__main__":
    result = test_image_with_full_pipeline("storage/captures/INJECTED/STATION_1_main_1793112337.jpg")
    sys.exit(0 if result.lower() == "scratch" else 1)
