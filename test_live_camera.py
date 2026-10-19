"""Live DroidCam test — runs the leather defect model on the camera feed.

Usage:
    python test_live_camera.py --url http://192.168.x.x:4747/video

Controls (OpenCV window):
    Q or ESC  — quit
    S         — save current frame as PNG
    P         — pause / unpause
"""

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# Make sure the src package is importable when run from project root
sys.path.insert(0, str(Path(__file__).parent / "src"))

from camerainspection.vision.station1 import SurfaceAnalyzer, LeatherDefectType

# Colour map per defect type (BGR)
DEFECT_COLORS: dict[LeatherDefectType, tuple[int, int, int]] = {
    LeatherDefectType.SCRATCH:        (0, 255, 255),   # yellow
    LeatherDefectType.CUT:            (0, 0, 255),     # red
    LeatherDefectType.PINHOLE:        (255, 0, 255),   # magenta
    LeatherDefectType.STAIN:          (0, 165, 255),   # orange
    LeatherDefectType.SHADE_BAND:     (255, 255, 0),   # cyan
    LeatherDefectType.COATING_STREAK: (128, 0, 255),   # purple
    LeatherDefectType.UNKNOWN:        (180, 180, 180), # grey
}


def draw_results(frame: np.ndarray, regions, fps: float, mode: str) -> np.ndarray:
    vis = frame.copy()
    h, w = vis.shape[:2]

    for r in regions:
        x, y, rw, rh = r.bbox_px
        color = DEFECT_COLORS.get(r.defect_type, (180, 180, 180))
        cv2.rectangle(vis, (x, y), (x + rw, y + rh), color, 2)
        label = f"{r.defect_type.value}  {r.anomaly_score:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        ty = max(y - 6, th + 4)
        cv2.rectangle(vis, (x, ty - th - 4), (x + tw + 6, ty + 2), color, -1)
        cv2.putText(vis, label, (x + 3, ty - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)

    # HUD
    status = f"Mode: {mode}  |  {len(regions)} defect(s)  |  {fps:.1f} fps"
    cv2.rectangle(vis, (0, 0), (w, 28), (20, 20, 20), -1)
    cv2.putText(vis, status, (8, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1, cv2.LINE_AA)
    return vis


def main() -> None:
    parser = argparse.ArgumentParser(description="Live leather defect test")
    parser.add_argument("--url", default="http://192.168.1.1:4747/video",
                        help="DroidCam MJPEG URL (default: %(default)s)")
    parser.add_argument("--model", default=None,
                        help="Path to ONNX model (default: models/station_1/model.onnx)")
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="Anomaly score threshold 0-1 (default: 0.5)")
    args = parser.parse_args()

    print(f"Connecting to {args.url} …")
    cap = cv2.VideoCapture(args.url)
    if not cap.isOpened():
        print("ERROR: Could not open camera URL. Check DroidCam is running and URL is correct.")
        sys.exit(1)

    analyzer = SurfaceAnalyzer(
        model_path=args.model,          # None → uses default path
        anomaly_threshold=args.threshold,
    )
    mode = "ONNX" if analyzer._session is not None else "Heuristic"
    print(f"Analyzer mode: {mode}")
    print("Press Q/ESC to quit, S to save frame, P to pause.")

    paused = False
    last_frame = None
    last_regions = []
    fps = 0.0
    t0 = time.perf_counter()
    frame_count = 0

    while True:
        if not paused:
            ret, frame = cap.read()
            if not ret:
                print("Stream lost — retrying…")
                time.sleep(0.5)
                cap.open(args.url)
                continue

            regions = analyzer.analyze(frame)
            last_frame = frame
            last_regions = regions

            frame_count += 1
            elapsed = time.perf_counter() - t0
            if elapsed >= 1.0:
                fps = frame_count / elapsed
                frame_count = 0
                t0 = time.perf_counter()

        if last_frame is not None:
            vis = draw_results(last_frame, last_regions, fps, mode)
            cv2.imshow("SeatGuard — Leather Inspection (live)", vis)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), 27):   # Q or ESC
            break
        elif key == ord('s') and last_frame is not None:
            fname = f"capture_{int(time.time())}.png"
            cv2.imwrite(fname, last_frame)
            print(f"Saved {fname}")
        elif key == ord('p'):
            paused = not paused
            print("Paused" if paused else "Resumed")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
