"""Unit tests for camera adapters and camera factory."""

from pathlib import Path
import cv2
import numpy as np
import pytest

from camerainspection.core.config import CameraConfig
from camerainspection.core.exceptions import (
    CameraOfflineError,
    CameraTimeoutError,
    CorruptImageError,
)
from camerainspection.hardware.camera.base import BaseCamera
from camerainspection.hardware.camera.factory import build_camera
from camerainspection.hardware.camera.replay import FolderReplayCamera
from camerainspection.hardware.camera.synthetic import SyntheticCamera
from camerainspection.hardware.camera.webcam import WebcamCamera


def test_synthetic_camera() -> None:
    cam = SyntheticCamera(width=320, height=240, pattern="stitch_line")
    with pytest.raises(CameraOfflineError):
        cam.capture()

    cam.connect()
    assert cam.is_connected() is True

    frame = cam.capture()
    assert frame.shape == (240, 320, 3)
    assert frame.dtype == np.uint8

    cam.disconnect()
    assert cam.is_connected() is False


def test_folder_replay_camera(tmp_path: Path) -> None:
    # Create 3 dummy test images in tmp_path
    img_dir = tmp_path / "replay_test"
    img_dir.mkdir()

    img1 = np.full((100, 100, 3), 50, dtype=np.uint8)
    img2 = np.full((100, 100, 3), 100, dtype=np.uint8)
    img3 = np.full((100, 100, 3), 150, dtype=np.uint8)

    cv2.imwrite(str(img_dir / "frame_01.png"), img1)
    cv2.imwrite(str(img_dir / "frame_02.png"), img2)
    cv2.imwrite(str(img_dir / "frame_03.png"), img3)

    cam = FolderReplayCamera(folder_path=img_dir, loop=False)
    with pytest.raises(CameraOfflineError):
        cam.capture()

    cam.connect()
    assert cam.is_connected() is True

    # Capture sequentially
    f1 = cam.capture()
    assert f1.mean() == 50

    f2 = cam.capture()
    assert f2.mean() == 100

    f3 = cam.capture()
    assert f3.mean() == 150

    # End of sequence with loop=False raises CameraTimeoutError
    with pytest.raises(CameraTimeoutError):
        cam.capture()

    cam.disconnect()


def test_folder_replay_camera_looping(tmp_path: Path) -> None:
    img_dir = tmp_path / "replay_loop"
    img_dir.mkdir()
    cv2.imwrite(str(img_dir / "f1.png"), np.zeros((50, 50, 3), dtype=np.uint8))

    cam = FolderReplayCamera(folder_path=img_dir, loop=True)
    cam.connect()
    _ = cam.capture()
    # Loops around smoothly
    _ = cam.capture()
    cam.disconnect()


def test_folder_replay_corrupt_file(tmp_path: Path) -> None:
    img_dir = tmp_path / "replay_corrupt"
    img_dir.mkdir()
    corrupt_file = img_dir / "bad.png"
    corrupt_file.write_text("not an image")

    cam = FolderReplayCamera(folder_path=img_dir, loop=False)
    cam.connect()
    with pytest.raises(CorruptImageError):
        cam.capture()
    cam.disconnect()


def test_camera_factory_selection(tmp_path: Path) -> None:
    # 1. Synthetic
    syn_cfg = CameraConfig(adapter="synthetic", resolution=[640, 480])
    cam = build_camera(syn_cfg)
    assert isinstance(cam, SyntheticCamera)

    # 2. Replay
    rep_cfg = CameraConfig(adapter="replay", replay_dir=str(tmp_path))
    cam = build_camera(rep_cfg)
    assert isinstance(cam, FolderReplayCamera)

    # 3. Webcam with int device
    web_cfg = CameraConfig(adapter="webcam", camera_id=0, resolution=[1280, 720])
    cam = build_camera(web_cfg)
    assert isinstance(cam, WebcamCamera)
    assert cam.camera_id == 0

    # 4. Webcam with URL string (phone IP camera)
    url_cfg = CameraConfig(adapter="webcam", camera_id="http://192.168.1.100:8080/video")
    cam = build_camera(url_cfg)
    assert isinstance(cam, WebcamCamera)
    assert cam.camera_id == "http://192.168.1.100:8080/video"

    # 5. CLI override
    cam = build_camera(rep_cfg, adapter_override="synthetic")
    assert isinstance(cam, SyntheticCamera)


def test_webcam_warning_logged(caplog: pytest.LogCaptureFixture) -> None:
    import logging
    with caplog.at_level(logging.WARNING):
        cam = WebcamCamera(camera_id="http://invalid.stream:8080/video")
        try:
            cam.connect()
        except Exception:
            pass
    assert any("Non-industrial camera" in r.message for r in caplog.records)
