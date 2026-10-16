#!/usr/bin/env python3
"""Interactive Live Camera & Phone Stream Tester for Station 1 (PatchCore ONNX).

Tests real-time surface anomaly detection on:
  1. USB / Integrated PC Webcam (--camera 0)
  2. Smartphone IP Camera Stream (--url "http://192.168.1.X:8080/video")
  3. Static Test Image (--image path/to/image.png)

Usage examples:
  # USB / Laptop Webcam:
  python tools/test_live_camera.py --camera 0

  # Smartphone IP Webcam (e.g. Android 'IP Webcam' or iOS 'DroidCam'):
  python tools/test_live_camera.py --url "http://192.168.1.50:8080/video"

  # Static test image:
  python tools/test_live_camera.py --image data/leather/test/scratch/000.png
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cv2
import numpy as np

from camerainspection.inference.onnx_patchcore import OnnxPatchCoreEngine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Live Camera / Phone Stream Inspector for Station 1 PatchCore Model"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Webcam device index (default: 0)",
    )
    group.add_argument(
        "--url",
        type=str,
        default=None,
        help="IP / RTSP stream URL from phone (e.g. http://192.168.1.50:8080/video)",
    )
    group.add_argument(
        "--image",
        type=Path,
        default=None,
        help="Path to a single image to test interactively",
    )
    parser.add_argument(
        "--weights",
        type=Path,
        default=Path("models/station_1/model.onnx"),
        help="Path to PatchCore ONNX weights (default: models/station_1/model.onnx)",
    )
    parser.add_argument(
        "--pass-below",
        type=float,
        default=0.40,
        help="Anomaly threshold below which outcome is PASS (default: 0.40)",
    )
    parser.add_argument(
        "--fail-above",
        type=float,
        default=0.60,
        help="Anomaly threshold above which outcome is FAIL (default: 0.60)",
    )
    return parser.parse_args()


def run_interactive() -> None:
    args = parse_args()

    weights_path = args.weights
    if not weights_path.exists():
        print(f"[ERROR] ONNX weights not found at: {weights_path}")
        print("Please ensure the PatchCore ONNX model is available.")
        sys.exit(1)

    print(f"[*] Initializing PatchCore ONNX engine from {weights_path}...")
    engine = OnnxPatchCoreEngine(
        pass_below=args.pass_below,
        fail_above=args.fail_above,
    )
    engine.load(weights_path)
    print(f"[*] Model loaded successfully ({engine.get_version()}).")
    print(f"[*] Thresholds: PASS < {args.pass_below:.2f} <= REVIEW < {args.fail_above:.2f} <= FAIL")

    # Image mode
    if args.image:
        if not args.image.exists():
            print(f"[ERROR] Image file not found: {args.image}")
            sys.exit(1)
        frame = cv2.imread(str(args.image))
        if frame is None:
            print(f"[ERROR] Failed to read image: {args.image}")
            sys.exit(1)
        _run_single_image(engine, frame, args.image.name)
        return

    # Video / Stream capture mode
    source = args.url if args.url else args.camera
    print(f"[*] Opening video source: {source} ...")
    cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        print(f"[ERROR] Could not open video source: {source}")
        if args.url:
            print("  Check that your phone and PC are on the same Wi-Fi network and the IP camera app is running.")
        else:
            print("  Check that your webcam is plugged in and accessible.")
        sys.exit(1)

    window_name = "SeatGuard Live Inspector (Station 1 - PatchCore)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1024, 768)

    print("\n" + "=" * 60)
    print(" LIVE INSPECTION RUNNING")
    print(" Controls:")
    print("   [q] or [ESC] : Quit")
    print("   [s]          : Save annotated snapshot")
    print("   [h]          : Toggle heatmap overlay on/off")
    print("   [SPACE]      : Freeze / unfreeze live frame")
    print("=" * 60 + "\n")

    show_heatmap = True
    frozen = False
    frozen_display: np.ndarray | None = None
    save_counter = 1
    fps_history: list[float] = []

    try:
        while True:
            if not frozen:
                t0 = time.perf_counter()
                ret, frame = cap.read()
                if not ret or frame is None:
                    print("[WARN] Failed to capture frame from video stream.")
                    time.sleep(0.1)
                    continue

                display_frame, score, outcome, hint = process_frame(
                    engine=engine,
                    frame=frame,
                    pass_below=args.pass_below,
                    fail_above=args.fail_above,
                    show_heatmap=show_heatmap,
                )
                t_elapsed = time.perf_counter() - t0
                fps = 1.0 / max(t_elapsed, 1e-4)
                fps_history.append(fps)
                if len(fps_history) > 30:
                    fps_history.pop(0)
                avg_fps = sum(fps_history) / len(fps_history)

                # Render HUD
                _draw_hud(display_frame, score, outcome, avg_fps, show_heatmap)
                frozen_display = display_frame
            else:
                display_frame = frozen_display if frozen_display is not None else frame

            cv2.imshow(window_name, display_frame)
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), 27):  # 'q' or ESC
                break
            elif key == ord("s"):
                out_dir = Path("storage/annotated_images")
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / f"live_snapshot_{save_counter:04d}.png"
                cv2.imwrite(str(out_path), display_frame)
                print(f"[INFO] Saved snapshot to: {out_path}")
                save_counter += 1
            elif key == ord("h"):
                show_heatmap = not show_heatmap
                print(f"[INFO] Heatmap display: {'ON' if show_heatmap else 'OFF'}")
            elif key == 32:  # SPACE
                frozen = not frozen
                print(f"[INFO] Stream {'FROZEN' if frozen else 'RESUMED'}")
    finally:
        cap.release()
        cv2.destroyAllWindows()


def process_frame(
    engine: OnnxPatchCoreEngine,
    frame: np.ndarray,
    pass_below: float,
    fail_above: float,
    show_heatmap: bool = True,
) -> tuple[np.ndarray, float, str, str]:
    """Run inference on the frame and draw overlays."""
    h, w = frame.shape[:2]
    annotated = frame.copy()

    # Preprocess & run ONNX session
    tensor = engine._preprocess(frame)
    outputs = engine._session.run(
        ["pred_score", "pred_label", "anomaly_map", "pred_mask"],
        {"input": tensor},
    )
    score = float(outputs[0][0])
    is_anomalous = bool(outputs[1][0])
    heatmap_raw = outputs[2][0, 0]  # (256, 256) float32
    mask = outputs[3][0, 0].astype(np.uint8) * 255

    # Determine outcome
    if is_anomalous or score >= fail_above:
        outcome = "FAIL"
        color = (0, 0, 255)  # Red
    elif score >= pass_below:
        outcome = "REVIEW"
        color = (0, 165, 255)  # Orange
    else:
        outcome = "PASS"
        color = (0, 255, 0)  # Green

    # Heatmap overlay
    if show_heatmap and (outcome != "PASS" or score >= pass_below * 0.7):
        # Normalize heatmap to 0-255 uint8
        hm_norm = cv2.normalize(heatmap_raw, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        hm_resized = cv2.resize(hm_norm, (w, h), interpolation=cv2.INTER_LINEAR)
        hm_color = cv2.applyColorMap(hm_resized, cv2.COLORMAP_JET)

        # Blend where mask or anomaly is active
        alpha = 0.35
        annotated = cv2.addWeighted(annotated, 1.0 - alpha, hm_color, alpha, 0)

    # Contours & bounding boxes
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    sx = w / 256.0
    sy = h / 256.0
    for cnt in contours:
        if cv2.contourArea(cnt) < 16:
            continue
        bx, by, bw, bh = cv2.boundingRect(cnt)
        x1 = max(0, int(bx * sx))
        y1 = max(0, int(by * sy))
        x2 = min(w, int((bx + bw) * sx))
        y2 = min(h, int((by + bh) * sy))

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            annotated,
            f"LEATHER_ANOMALY {score:.2f}",
            (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2,
        )

    return annotated, score, outcome, ("FAIL" if is_anomalous or score >= fail_above else "REVIEW")


def _draw_hud(frame: np.ndarray, score: float, outcome: str, fps: float, show_heatmap: bool) -> None:
    """Draw top status banner on frame."""
    h, w = frame.shape[:2]
    # Header bar background
    cv2.rectangle(frame, (0, 0), (w, 55), (25, 25, 25), -1)

    # Color code outcome
    if outcome == "PASS":
        out_col = (0, 255, 0)
    elif outcome == "REVIEW":
        out_col = (0, 165, 255)
    else:
        out_col = (0, 0, 255)

    cv2.putText(
        frame,
        f"OUTCOME: {outcome}",
        (20, 38),
        cv2.FONT_HERSHEY_DUPLEX,
        1.0,
        out_col,
        2,
    )

    cv2.putText(
        frame,
        f"Score: {score:.3f}",
        (320, 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
    )

    cv2.putText(
        frame,
        f"FPS: {fps:.1f}",
        (540, 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (200, 200, 200),
        1,
    )

    hm_text = f"Heatmap: {'ON' if show_heatmap else 'OFF'} [h]"
    cv2.putText(
        frame,
        hm_text,
        (w - 240, 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (180, 180, 180),
        1,
    )


def _run_single_image(engine: OnnxPatchCoreEngine, frame: np.ndarray, name: str) -> None:
    annotated, score, outcome, _ = process_frame(
        engine=engine,
        frame=frame,
        pass_below=engine.pass_below,
        fail_above=engine.fail_above,
        show_heatmap=True,
    )
    _draw_hud(annotated, score, outcome, fps=0.0, show_heatmap=True)

    window_name = f"SeatGuard Single Image Inspection - {name}"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.imshow(window_name, annotated)
    print(f"\n[RESULT] {name}: Score={score:.3f} -> {outcome}")
    print("Press any key to close the window...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run_interactive()
