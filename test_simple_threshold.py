#!/usr/bin/env python3
"""Simple test to verify threshold routing and basic ONNX operation."""

import sys
from pathlib import Path
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "src"))

from camerainspection.core.config import load_station_config
from camerainspection.station.station_1 import Station1Service
from camerainspection.core.limits import LimitsEvaluator
import yaml

# Load limits
limits_path = Path("configs/variants/default_limits.yaml")
with open(limits_path) as f:
    limits_data = yaml.safe_load(f).get("limits", {})

# Create station with threshold=0.55
station_cfg = load_station_config(Path("configs/stations/station_1_leather.yaml"))
station_cfg.model.threshold = 0.55

print("Config after setting threshold=0.55:")
print(f"  model.threshold: {station_cfg.model.threshold}")
print(f"  model.backend: {station_cfg.model.backend}")
print(f"  model.weights_path: {station_cfg.model.weights_path}")

variants_root = Path("configs/variants")
station = Station1Service(
    station_config=station_cfg,
    variants_root=variants_root,
    default_limits_path=limits_path,
)

print("\nAfter Station1Service.__init__:")
print(f"  config.model.pass_below: {station.config.model.pass_below}")
print(f"  config.model.fail_above: {station.config.model.fail_above}")
print(f"  config.model.backend: {station.config.model.backend}")

expected_pass = 0.55 - 0.05  # 0.50
expected_fail = 0.55 + 0.15  # 0.70

if abs(station.config.model.pass_below - expected_pass) < 0.01:
    print(f"\nOK: pass_below correctly set to {station.config.model.pass_below}")
else:
    print(f"\nFAIL: pass_below is {station.config.model.pass_below}, expected {expected_pass}")
    sys.exit(1)

if abs(station.config.model.fail_above - expected_fail) < 0.01:
    print(f"OK: fail_above correctly set to {station.config.model.fail_above}")
else:
    print(f"FAIL: fail_above is {station.config.model.fail_above}, expected {expected_fail}")
    sys.exit(1)

# Test with a clean image
clean_img = np.full((1024, 1024, 3), 50, dtype=np.uint8)

evaluator = LimitsEvaluator(limits_data)
defects, measurements, annotated = station.inspect_image(
    image=clean_img,
    variant_id="FRONT_LH_BLACK",
    evaluator=evaluator,
    variant_nominals={},
)

print(f"\nTest with clean black image:")
print(f"  Defects in list: {len(defects)}")
print(f"  seating_face.defect_count: {measurements.get('seating_face.defect_count', 'MISSING')}")
print(f"  leather.anomaly_score: {measurements.get('leather.anomaly_score', 'MISSING')}")
print(f"  anomaly_threshold: {measurements.get('seating_face.anomaly_threshold', 'MISSING')}")

if len(defects) > 0:
    print(f"\nDefects:")
    for d in defects:
        print(f"  - {d.defect_type}: {d.outcome.value} conf={d.confidence:.3f}")

print("\n" + "="*80)
print("Threshold routing test: PASSED")
print("="*80)
