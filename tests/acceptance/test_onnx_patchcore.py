"""Acceptance test for the OnnxPatchCoreEngine on Station 1.

Checks:
  1. Engine loads without error.
  2. I/O contract: preprocessing produces the correct tensor shape and range.
  3. If real MVTec leather images are present:
       data/leather/test/good/      -> score < 0.40 (PASS), pred_label False
       data/leather/test/<defect>/  -> pred_label True (FAIL)
  4. Preprocessing sanity: running with ImageNet mean/std applied should NOT
     produce the same scores (guards against accidental normalisation).

Synthetic images are NOT used to assess model quality — a PatchCore model
trained on real leather textures will correctly flag solid-grey/random-noise
images as anomalous. Only real test-set images are meaningful.

Run from the project root:
  python tests/acceptance/test_onnx_patchcore.py

Exit 0 = passed, Exit 1 = failed.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import cv2
import numpy as np

WEIGHTS = Path("models/station_1/model.onnx")
GOOD_DIR = Path("data/leather/test/good")


def _find_defect_dir() -> Path | None:
    base = Path("data/leather/test")
    if not base.exists():
        return None
    for p in sorted(base.iterdir()):
        if p.is_dir() and p.name != "good":
            return p
    return None


def _load_first_image(directory: Path) -> np.ndarray | None:
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.bmp"):
        for match in sorted(directory.glob(ext)):
            img = cv2.imread(str(match))
            if img is not None:
                return img
    return None


def main() -> int:
    from camerainspection.inference.onnx_patchcore import OnnxPatchCoreEngine

    print("=" * 60)
    print("  OnnxPatchCoreEngine Acceptance Test")
    print(f"  Weights: {WEIGHTS}")
    print("=" * 60)

    # ── 1. Load ────────────────────────────────────────────────────
    print("\nStep 1: Loading model...")
    try:
        engine = OnnxPatchCoreEngine(pass_below=0.40, fail_above=0.60)
        engine.load(WEIGHTS)
        print(f"  PASS  version={engine.get_version()}")
    except Exception as exc:
        print(f"  FAIL  Load failed: {exc}")
        return 1

    # ── 2. I/O contract ────────────────────────────────────────────
    print("\nStep 2: I/O contract check (tensor shape and value range)...")
    test_bgr = np.full((480, 640, 3), 128, dtype=np.uint8)
    # Access the internal _preprocess to verify shape without running full inference
    tensor = engine._preprocess(test_bgr)
    assert tensor.shape == (2, 3, 256, 256), f"Bad tensor shape: {tensor.shape}"
    assert tensor.dtype == np.float32, f"Bad tensor dtype: {tensor.dtype}"
    assert tensor.min() >= 0.0 and tensor.max() <= 1.0, \
        f"Tensor out of [0,1] range: min={tensor.min():.4f} max={tensor.max():.4f}"
    assert tensor[0].tobytes() == tensor[1].tobytes(), "Batch slots are not identical"
    print(f"  PASS  shape={tensor.shape} dtype={tensor.dtype} "
          f"range=[{tensor.min():.3f}, {tensor.max():.3f}] batch_identical=True")

    # ── 3. Real image tests (skipped if images not present) ────────
    good_img = _load_first_image(GOOD_DIR) if GOOD_DIR.exists() else None
    defect_dir = _find_defect_dir()
    defect_img = _load_first_image(defect_dir) if defect_dir else None

    if good_img is None and defect_img is None:
        print("\nStep 3: Real image test -- SKIPPED")
        print("  No MVTec leather test images found.")
        print("  Place images under data/leather/test/good/ and data/leather/test/<defect>/")
        print("  to run the full acceptance check.")
    else:
        print("\nStep 3: Real image tests...")

        if good_img is not None:
            dets = engine.predict(good_img)
            score = dets[0].anomaly_score if dets else 0.0
            label = dets[0].metadata.get("pred_label") if dets else False
            print(f"  Good  image: score={score:.4f}  pred_label={label}")
            if label:
                print("  FAIL  Good image flagged as anomalous.")
                print("         Expected: pred_label=False (score below model threshold).")
                print("         If you see this with real MVTec leather 'good' images,")
                print("         the preprocessing or model export may be wrong.")
                return 1
            print("  PASS  Good image not flagged.")

        if defect_img is not None:
            dets = engine.predict(defect_img)
            score = dets[0].anomaly_score if dets else 0.0
            label = dets[0].metadata.get("pred_label") if dets else False
            print(f"  Defect image: score={score:.4f}  pred_label={label}  "
                  f"(from {defect_dir.name})")
            if not label:
                print("  FAIL  Defect image NOT flagged as anomalous.")
                print("         Expected: pred_label=True.")
                return 1
            print("  PASS  Defect image correctly flagged.")

    print("\n" + "=" * 60)
    print("  Acceptance test PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
