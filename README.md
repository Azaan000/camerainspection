# Automated Camera Inspection System for Automotive Seats

High-reliability, automated end-of-line (EOL) computer vision inspection system for automotive seats featuring multi-camera image acquisition, sub-pixel dimensional metrology, deep learning defect segmentation, hardware PLC interlocks, and full traceability.

---

## 1. Safety Invariants & Architecture Rules

1. **Strict Fail-Closed Architecture**:
   - Any ambiguity (missing barcode/RFID, unknown variant, disconnected camera, unverified lighting, missing/expired calibration, trigger timeout, or hardware fault) produces `FAIL` or `REVIEW`, **never `PASS`**.
   - By default, the pallet clamp holds the unit at the station until explicit clearance.
2. **Label Printer Hardware Interlock**:
   - The OEM shipping label printer is electrically and logically interlocked.
   - It is armed **only when all four inspection stations record `PASS`**, the Station 4 mechanism load/travel test passes, and the physical mechanism lock sensor is verified closed.
   - Any failure or subsequent seat arrival immediately disables the label printer.
3. **No Hardcoded Constants**:
   - All dimensional thresholds, color tolerances, nominals, and regions of interest (ROIs) reside in version-controlled YAML files under `configs/`.
4. **Traceability & OEM Compliance**:
   - Every seat inspection generates an immutable audit record in SQLite/PostgreSQL with defect bounding boxes, camera telemetry, and downloadable trace archives (`/api/v1/seats/{id}/export`).

---

## 2. System Architecture

```text
       ┌─────────────────────────────────────────────────────────────┐
       │                Main Conveyor Transport Line                │
       └──────────────────────────────┬──────────────────────────────┘
                                      │
  ┌─────────────────┬─────────────────┼─────────────────┬─────────────────┐
  ▼                 ▼                 ▼                 ▼                 ▼
Station 1         Station 2         Station 3         Station 4      Label Printer
Leather & Trim    Seams & Stitch    Child Seat & Acc  Recliner Mech  Interlock Gate
2 Cameras         4 Cameras         3 Cameras         3 Cameras      (All 4 PASS)
  │                 │                 │                 │                 │
  └────────►────────┴────────►────────┴────────►────────┴────────►────────┘
                                      │
                                      ▼
                        Inspection Coordinator & PLC
                  (Watchdog Heartbeat, Pallet Clamps & Diverter)
                                      │
                      ┌───────────────┴───────────────┐
                      ▼                               ▼
               FastAPI Backend                SeatGuard Web UI
         (REST API, Auth & Export)        (Rework Bench & Dashboards)
```

---

## 3. Station Multi-Camera Layout

| Station | Focus Area | Mapped Camera Views | Detection Modalities |
| :--- | :--- | :--- | :--- |
| **Station 1** | Leather & Surface | `front_cushion_backrest`<br>`rear_back_map_pocket` | Scratches, cuts, pinholes, stains, wrinkles, foam show-through |
| **Station 2** | Seams & Stitching | `left_bolster`<br>`right_bolster`<br>`headrest`<br>`seam_arm` | Broken threads, skipped stitches, stitch density, thread color ($\Delta E$) |
| **Station 3** | Assemblies & Safety | `belt_buckle_front`<br>`child_seat_lower`<br>`headrest_guide` | ISOFIX bars, buckle presence/hand, guide sleeves, shield gaps |
| **Station 4** | Mechanisms & Rails | `recliner_pivot`<br>`track_sensor_rail`<br>`lumbar_side_flange` | Recliner angle, lock torque ($>35\text{ N}\cdot\text{m}$), slip-back ($<0.5\text{ mm}$), lever position |

---

## 4. Hardware Support & Adapters

- **Cameras**:
  - `synthetic`: Procedural synthetic image generation for testing and CI/CD.
  - `replay`: Replays golden and defect datasets from directory structures.
  - `webcam`: USB UVC webcams (device index `0`, `1`) or IP camera streams / RTSP URLs (e.g. `http://192.168.1.50:8080/video`).
  - `basler`: Basler Ace/Dart GigE & USB3 industrial cameras via PyPylon (lazy SDK loading).
  - `hikrobot`: Hikrobot MVS industrial GigE & USB3 cameras (lazy SDK loading).
- **PLC Controllers**:
  - `simulator`: Thread-safe software simulator tracking tags, hold states, and printer coils.
  - `modbus`: Modbus TCP / RTU PLC adapter.
  - `snap7`: Siemens S7-1200 / S7-1500 communication via python-snap7.
  - `opcua`: OPC-UA industrial server integration.
- **Lighting & Fixtures**:
  - Programmable multi-channel LED lighting controllers via Modbus RTU / TCP with readback verification.
  - Pneumatic pallet clamps and rotating turntable / robot arm fixtures with in-position feedback.
- **Tracking & Line Hardware**:
  - Industrial RFID tag readers (Balluff, Sick, Siemens) via serial / USB.
  - Line conveyor motors and pneumatic reject spur diverter gates.
  - Operator pushbutton panels (Start, Stop, Reset, Emergency-Stop) with stack lights.

---

## 5. Quickstart & Usage

### Running Tests
```bash
# Run complete test suite
pytest tests/ -v

# Run with test coverage
pytest tests/ -v --cov=camerainspection --cov-report=term-missing
```

### Running with Real Webcams or Phone IP Cameras
```bash
# Test with default local USB webcam
python -m camerainspection.main --camera-adapter webcam

# Test with phone IP camera app (e.g. IP Webcam on Android/iOS)
python -m camerainspection.main --camera-adapter webcam --camera-url "http://192.168.1.85:8080/video"
```

### Camera Calibration Tool
Calibrate industrial cameras using an $8 \times 6$ or $9 \times 6$ checkerboard pattern:
```bash
python tools/calibrate_camera.py --camera-name main --images-dir ./data/calibration_images/ --square-size-mm 25.0
```

### End-of-Shift Quality Report (Shadow Mode)
Calculate agreement, false-reject rate, and escape rate comparing vision model against human inspector review:
```bash
python tools/shift_report.py --db-url "sqlite:///./data/inspection.db" --alert-threshold-pct 3.0
```

### Automated Acceptance Test Suite
Execute end-to-end line acceptance test running 100 known-good seats and 6 seeded safety defect seats (asserts 100% reject diversion with zero escapes):
```bash
python tools/acceptance_test.py --clean-seats 100
```

---

## 6. Docker Deployment (PostgreSQL)

```bash
# Start PostgreSQL database and inspection service
docker compose -f docker/docker-compose.yml up --build

# Run in background
docker compose -f docker/docker-compose.yml up -d
```

---

## 7. Web Dashboard & Operator Rework Bench

The single-page web UI (`ui/index.html`) provides dark-mode monitoring and rework management:
- **Live Line View**: 20-seat status strip, line throughput, and live cycle times.
- **Quality Trends**: Pass/Review/Fail breakdown and defect Pareto distribution.
- **Defect Gallery**: Visual defect browsing with bounding boxes and measurements.
- **Human Review Queue**: Inspector adjudication for held units.
- **Rework Bench (Phase 9)**: Barcode/RFID lookup, multi-camera views, failing rule evaluation, operator rework dispositions, and one-click OEM traceability ZIP export.
- **Shadow Mode Analytics**: Human vs. camera agreement matrix and false-reject alerts.

-	echo $env:INSPECTION_API_KEY should print the key.
-	python -m camerainspection.main