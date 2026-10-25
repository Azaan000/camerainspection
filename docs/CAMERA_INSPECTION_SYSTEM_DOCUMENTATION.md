# Automated Camera Inspection System
## Comprehensive Technical Documentation

---

# Table of Contents

1. [System Overview](#1-system-overview)
2. [System Architecture](#2-system-architecture)
3. [Shadow Mode](#3-shadow-mode)
4. [Inspection Stations](#4-inspection-stations)
5. [Hardware Components](#5-hardware-components)
6. [Vision and AI Features](#6-vision-and-ai-features)
7. [Dashboard Features](#7-dashboard-features)
8. [API Endpoints](#8-api-endpoints)
9. [Quality Control Features](#9-quality-control-features)
10. [Configuration](#10-configuration)
11. [Safety and Interlocks](#11-safety-and-interlocks)

---

# 1. System Overview

The **Automated Camera Inspection System** is an end-of-line (EOL) quality inspection solution for automotive seat manufacturing. The system performs automated visual inspection at four different stations along the production line, using machine vision and AI to detect defects and ensure product quality.

## Key Capabilities

- **Multi-Station Inspection**: Four inspection stations covering leather, stitching, plastic components, and mechanism testing
- **AI-Powered Defect Detection**: Uses ONNX models, YOLO, and PatchCore for anomaly detection
- **Shadow Mode Operation**: Can run in shadow mode for validation without physical output
- **Real-Time Monitoring**: Live dashboard showing line status and quality metrics
- **Human-in-the-Loop**: Review queue for ambiguous inspections requiring human judgment
- **Audit Trail**: Complete traceability for OEM compliance

---

# 2. System Architecture

## 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTOMATED CAMERA INSPECTION                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐     │
│  │STATION 1 │   │STATION 2 │   │STATION 3 │   │STATION 4 │     │
│  │ Leather  │──▶│ Stitch   │──▶│ Plastic  │──▶│Mechanism │     │
│  │ Surface  │   │ Quality  │   │ Presence │   │  Cycle   │     │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘     │
│       │              │              │              │            │
│       └──────────────┴──────────────┴──────────────┘            │
│                           │                                      │
│                    ┌──────▼──────┐                               │
│                    │ COORDINATOR │                               │
│                    │  Service    │                               │
│                    └──────┬──────┘                               │
│                           │                                      │
│     ┌─────────────────────┼─────────────────────┐               │
│     │                     │                     │               │
│ ┌───▼───┐           ┌─────▼─────┐         ┌─────▼─────┐         │
│ │  PLC  │           │ Database  │         │  Label    │         │
│ │Inter- │           │  (SQLite) │         │ Printer   │         │
│ │ lock  │           │           │         │           │         │
│ └───────┘           └───────────┘         └───────────┘         │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    DASHBOARD / API                        │  │
│  │  (FastAPI + React Frontend)                               │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 2.2 Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.13+, FastAPI |
| Database | SQLite (production), with SQLAlchemy ORM |
| AI Inference | ONNX Runtime, YOLO, PatchCore |
| Camera Adapters | Replay, Synthetic, Webcam, Basler, Hikrobot |
| PLC Communication | Simulator, Modbus, Snap7, OPC-UA |
| Frontend | React + TypeScript + Vite |
| API Documentation | Swagger/OpenAPI |

## 2.3 Core Components

### Inspection Coordinator
The `InspectionCoordinator` service orchestrates multi-station aggregation and label gating. It manages the complete inspection cycle for each seat, aggregating results from all four stations and enforcing safety interlocks.

### Line Controller
The `LineController` manages conveyor sequences, emergency stop functionality, and reject diversion. It controls physical material handling and ensures pallets move correctly through the line.

### Database Manager
SQLite-based persistence with tables for:
- Seat inspection records
- Station results
- Defect records
- Audit logs
- Human review records
- Shadow decisions

---

# 3. Shadow Mode

## 3.1 What is Shadow Mode?

**Shadow Mode** is a critical operating mode where the system logs all inspection decisions and tracks quality metrics WITHOUT driving physical outputs. In shadow mode:

- ✅ Inspection results are computed normally
- ✅ AI models run inference
- ✅ Defects are detected and recorded
- ✅ Database records are persisted
- ✅ Audit logs are maintained
- ❌ **PLC pallet hold is NOT activated**
- ❌ **Label printer is NOT triggered**
- ❌ **Physical conveyor is NOT controlled**

## 3.2 When to Use Shadow Mode

| Scenario | Recommendation |
|----------|----------------|
| Initial system deployment | Run in shadow mode for 1-2 weeks |
| AI model validation | Compare AI decisions vs human inspector |
| System maintenance | Run shadow mode during troubleshooting |
| New variant introduction | Validate before full production |
| Software updates | Shadow mode to verify stability |

## 3.3 Shadow Mode Behavior Details

### Without Shadow Mode (Production)

```
Seat Arrives → Station 1 → Station 2 → Station 3 → Station 4
                                                      │
                                          All PASS + Mechanism OK
                                                      │
                                          ┌──────────▼──────────┐
                                          │ Enable Label Printer│
                                          │ Hold Pallet         │
                                          │ Release to Mainline │
                                          └─────────────────────┘
```

### With Shadow Mode (Validation)

```
Seat Arrives → Station 1 → Station 2 → Station 3 → Station 4
                                                      │
                                          All PASS + Mechanism OK
                                                      │
                                          ┌──────────▼──────────┐
                                          │ LOG Decision Only   │
                                          │ NO Physical Action  │
                                          │ Queue for Audit     │
                                          └─────────────────────┘
```

## 3.4 Configuration

In `configs/system.yaml`:

```yaml
system:
  environment: "development"
  shadow_mode: false  # Set to true to enable
  operating_mode: "camera_leads_with_audit"  # or "shadow"
```

At runtime via API:
```bash
POST /api/v1/system/shadow-mode
{"enabled": true}
```

## 3.5 Shadow Mode Statistics

The system tracks shadow mode performance through:
- **Shadow Decision Recording**: Human inspector decisions are recorded alongside AI decisions
- **Escape Tracking**: AI PASS but human FAIL (defects that AI missed)
- **False Reject Tracking**: AI FAIL but human PASS (over-rejection)
- **Agreement Rate**: Percentage of AI decisions matching human judgment

---

# 4. Inspection Stations

## 4.1 Station 1: Leather / Rexene Panel Inspection

### Purpose
Inspect dark surfaces (leather/rexene) for cosmetic defects using anomaly detection and segmentation.

### Configuration
- **Camera**: 2592×1944 resolution, 0.18mm pixel size
- **Lighting**: Dome (80%) + Low-angle (60%)
- **Model**: Anomalib PatchCore (ONNX)
- **Detection Target**: 0.45 threshold

### Camera Views
1. **Front Cushion Backrest**
   - ROI: Seating face area
   
2. **Rear Back Map Pocket**
   - ROI: Side back area

### Defects Detected
- Scratches
- Cuts
- Pinholes
- Stains
- Surface anomalies (wrinkles, discoloration)

### Inspection Process
1. Wait for PLC trigger
2. Read barcode (extract seat ID + variant)
3. Configure dome and low-angle lighting
4. Capture image from each camera
5. Run PatchCore anomaly detection
6. Evaluate against thresholds (pass_below: 0.4, fail_above: 0.6)
7. Generate annotated image with defect bounding boxes
8. Persist results to database
9. Report outcome to PLC (unless shadow mode)

---

## 4.2 Station 2: Stitching Inspection

### Purpose
Rule-based measurement for stitches and position; AI model for broken thread and loose ends.

### Configuration
- **Camera**: 2592×1944 resolution, 0.08mm pixel size (high precision)
- **Lighting**: Direct intensity 90%
- **Model**: YOLO stitch defect detection (ONNX)
- **Detection Target**: 0.50 threshold

### Camera Views
1. **Left Bolster**
2. **Right Bolster**
3. **Headrest**
4. **Seam Arm** (robot-arm camera with multiple poses)

### Measurements
- **Stitches Per Inch (SPI)**: Target 7.0, tolerance ±0.5
- **Seam Position**: Deviation from nominal, ±1.5mm
- **Stitch Pitch Delta**: Deviation from nominal

### Defects Detected
- Broken thread
- Skip stitch
- Loose thread ends
- Wrong thread color

### Inspection Process
1. Wait for trigger
2. Configure lighting
3. Capture from multiple cameras
4. Apply AI model for defect detection
5. Apply rule-based measurement for stitch quality
6. Evaluate against limits
7. Record all measurements and defects

---

## 4.3 Station 3: Plastic Parts and Shield Inspection

### Purpose
Presence detection, correct hand (LH/RH), color match, golden image matching, crack and short shot detection.

### Configuration
- **Camera**: 2592×1944 resolution, 0.18mm pixel size
- **Lighting**: Diffuse intensity 85%
- **Model**: YOLO presence detection (ONNX)
- **Detection Target**: 0.40 threshold

### Camera Views
1. **Side Shield Handle Lever**
   - ROI: Side shield area
   - ROI: Lever handle area
   
2. **Underside**
   - ROI: Underside clips area

### Features
- **Golden Image Matching**: Compare against reference images with 0.85 threshold
- **Color Check**: Verify plastic color matches variant specification
- **Hand Verification**: Confirm LH vs RH configuration

### Measurements
- **Shield Gap**: Target 2.5mm, tolerance 0.5-4.5mm
- **Flash/Burr Protrusion**: Target 0mm, max 0.5mm

### Defects Detected
- Part missing
- Part wrong (incorrect variant)
- Part incorrect orientation
- Plastic cracks
- Short shots (incomplete molding)

---

## 4.4 Station 4: Complete Seat & Mechanism Cycle Test

### Purpose
Cosmetics inspection, component presence verification, full travel recliner and track testing, sensor lock confirmation.

### Configuration
- **Camera**: 2592×1944 resolution, 0.15mm pixel size
- **Lighting**: Ambient 100%
- **Model**: YOLO cosmetic defects (ONNX)
- **Detection Target**: 0.45 threshold

### Camera Views
1. **Recliner Track**
   - ROI: Recliner pivot area
   - ROI: Track travel area

### Mechanism Testing
- **Full Cycle Command**: Trigger recliner through full range
- **Sensor Poll Timeout**: 10 seconds
- **Lock Verification**: Strict sensor confirmation required
- **Minimum Lock Torque**: 15.0 Nm
- **Maximum Slip Back**: 1.0mm

### Measurements
- **Recliner Angle**: Target 90°, tolerance 88-92°
- **Track Position**: Target 240mm, tolerance 238-242mm

### Defects Detected
- Wrinkle/puckering
- Foam showthrough
- Recliner angle deviation
- Track position deviation

### Safety Interlock
This station is critical for the label printer enable:
- All stations must PASS
- Mechanism cycle must PASS
- Lock sensor must be confirmed
- THEN label printer can be enabled

---

# 5. Hardware Components

## 5.1 Camera Adapters

The system supports multiple camera adapters for flexibility:

| Adapter | Use Case | Description |
|---------|----------|-------------|
| `replay` | Development/Testing | Replay captured images from disk |
| `synthetic` | Testing | Generate synthetic test images |
| `webcam` | Development | USB webcam for live testing |
| `basler` | Production | Basler industrial cameras |
| `hikrobot` | Production | Hikrobot industrial cameras |
| `phone` | Development | Android phone camera via DroidCam |
| `rtsp` | Production | RTSP stream from network camera |
| `ip` | Production | Direct IP camera connection |

### Camera Configuration Example
```yaml
cameras:
  - name: front_cushion_backrest
    view: front_cushion_backrest
    enabled: true
    adapter: replay
    replay_dir: data/station_1/replay/front_cushion_backrest
    resolution: [2592, 1944]
    exposure_us: 15000
    gain_db: 0.0
    pixel_size_mm: 0.18
    timeout_ms: 3000
    regions_of_interest:
      seating_face:
        x: 200
        y: 200
        w: 2200
        h: 1500
```

## 5.2 PLC Integration

### Supported PLC Adapters

| Adapter | Protocol | Use Case |
|---------|----------|----------|
| `simulator` | Internal | Development/Testing |
| `modbus` | Modbus TCP | Industrial integration |
| `snap7` | S7 Protocol | Siemens S7 PLCs |
| `opcua` | OPC-UA | Modern industrial systems |

### PLC Functions
- **Trigger Reception**: Wait for station trigger signal
- **Barcode Reading**: Read seat/barcode from PLC
- **Station Result**: Report PASS/FAIL/REVIEW to PLC
- **Pallet Hold**: Hold/release pallet at station
- **Label Printer**: Enable/disable label printer
- **Lock Sensor**: Read mechanism lock status
- **Emergency Stop**: Line-wide E-Stop control

## 5.3 Lighting Control

### Lighting Channels
- **Dome**: Uniform overhead lighting for surface inspection
- **Low-Angle**: Side lighting for texture/scratch detection
- **Direct**: Focused lighting for stitch inspection
- **Diffuse**: Even lighting for plastic inspection
- **Ambient**: General area lighting

### Control Features
- Intensity percentage (0-100%)
- Verification read-back
- Per-camera lighting profiles
- Hardware presence enforcement

## 5.4 RFID & Barcode

- **RFID Writer**: Write seat ID to RFID tag
- **Barcode Scanner**: Read barcode at each station
- **Variant Resolution**: Extract variant from barcode (format: `SEAT_ID:VARIANT_ID`)

## 5.5 Conveyor & Diverter

- **Mainline Release**: PASS seats go to main conveyor
- **Reject Diverter**: FAIL/REVIEW seats diverted to reject spur
- **Emergency Stop**: Stop all conveyor movement

## 5.6 Operator Panel

- **Red Indicator**: FAIL/REVIEW state
- **Green Indicator**: PASS state
- **Amber Indicator**: Standby/E-Stop reset

---

# 6. Vision and AI Features

## 6.1 AI Models

### PatchCore (Station 1)
- Anomaly detection using PatchCore algorithm
- Trained on normal (good) seat surfaces
- Outputs anomaly score: 0.0 (normal) to 1.0 (anomalous)
- Thresholds: pass_below: 0.4, fail_above: 0.6

### YOLO Models (Stations 2-4)
- Object detection for specific defect classes
- Bounding box detection with confidence scores
- Multi-class detection support

### ONNX Runtime
- Cross-platform inference
- Hardware acceleration support
- Model versioning and management

## 6.2 Classical Vision

### Edge Detection
- Canny edge detection for surface inspection
- Contour analysis for measurements

### Color Analysis
- BGR/HSV color space analysis
- Color matching against golden references

### Template Matching
- Golden image comparison
- NCC-based matching with configurable threshold

## 6.3 Measurement Systems

### Pixel-to-Millimeter Conversion
- Calibration-based conversion using pixel_size_mm
- Per-camera calibration support

### Limit Evaluation
- **Range Limits**: value <= pass_max (PASS), pass_max < value < fail_at (REVIEW), >= fail_at (FAIL)
- **Tolerance Limits**: |value - nominal| <= pass_tol (PASS), <= fail_tol (REVIEW), > fail_tol (FAIL)
- **Boolean Rules**: Immediate FAIL/REVIEW on detection

---

# 7. Dashboard Features

## 7.1 Live Line View (`/api/v1/dashboard/live`)

- Real-time 20-seat strip showing pass/fail status
- Current seat ID display
- Label printer status per seat
- Timestamp for each inspection

## 7.2 Quality Trends (`/api/v1/dashboard/quality-trends`)

- Pass rate, review rate, fail rate calculations
- Defect Pareto chart (defect type frequency)
- Sample size tracking

## 7.3 Defect Gallery (`/api/v1/dashboard/defect-gallery`)

- Browse all detected defects
- Filter by station, defect type
- Image display with bounding boxes
- Defect metadata (measured value, nominal, delta)

## 7.4 Live Companion View (`/api/v1/dashboard/live-companion`)

- Latest seat inspection snapshots
- Per-station views and outcomes
- Golden reference images for variant
- Nominal specifications display

## 7.5 Shadow Mode Statistics (`/api/v1/dashboard/shadow-mode`)

- Camera vs inspector agreement rate
- Escape tracking (AI miss rate)
- False reject tracking
- Shift-based reporting

## 7.6 System Health (`/api/v1/dashboard/system-health`)

- PLC connection status
- Database health
- Operating mode display
- Per-station status and model versions

## 7.7 Review Queue (`/api/v1/reviews/pending`)

- List inspections in REVIEW state
- Human inspector decision interface
- Decision options: PASS, REWORK, SCRAP

## 7.8 Shift Report (`/api/v1/dashboard/shift-report`)

- Comprehensive end-of-shift quality report
- Camera vs inspector comparison
- False reject threshold configuration
- Defect escape analysis

## 7.9 SPC Charts (`/api/v1/analytics/spc-measurements`)

- Statistical Process Control X-bar charts
- Metrics: SPI, seam position, shield gap, recliner angle, track position
- Control limits (UCL, LCL) calculation
- Cpk analysis
- Trend visualization

## 7.10 Audit Log (`/api/v1/audit`)

- Immutable audit trail
- Filter by seat ID
- Event type tracking
- Timestamp recording

---

# 8. API Endpoints

## 8.1 Station Result Ingestion

```
POST /api/v1/stations/result
```

Submit station inspection results from camera nodes.

## 8.2 Seat Status

```
GET /api/v1/seats/{seat_id}
```

Retrieve complete inspection history and outcome for a seat.

## 8.3 Export

```
GET /api/v1/seats/{seat_id}/export
```

Export seat trace as ZIP (JSON + images) or JSON.

## 8.4 Review Queue

```
GET  /api/v1/reviews/pending       # List pending reviews
POST /api/v1/reviews/{id}/decision # Submit decision
```

## 8.5 Shadow Mode

```
POST /api/v1/shadow-mode/decision  # Record inspector decision
GET  /api/v1/dashboard/shadow-mode # View statistics
```

## 8.6 Audit Sampling

```
POST /api/v1/audit/sample              # Generate random sample
GET  /api/v1/audit/samples             # List samples
POST /api/v1/audit/sample/{id}/decision # Submit audit decision
```

## 8.7 System Settings

```
GET    /api/v1/system/settings      # Get current settings
POST   /api/v1/system/save-images   # Toggle image saving
POST   /api/v1/system/shadow-mode   # Toggle shadow mode
POST   /api/v1/system/cleanup-images # Cleanup old images
```

## 8.8 Camera Management

```
GET /api/v1/cameras/detect          # Detect connected cameras
GET /api/v1/cameras/test            # Test camera connection
GET /api/v1/cameras/snapshot        # Capture snapshot
GET /api/v1/cameras/config          # Get camera configs
POST /api/v1/cameras/config         # Update camera config
GET /api/v1/cameras/all-status      # All cameras status
```

## 8.9 Station Configuration

```
GET /api/v1/stations/{id}/rois       # Get ROIs
POST /api/v1/stations/{id}/rois      # Update ROIs
POST /api/v1/stations/{id}/inject-image # Test with injected image
```

## 8.10 Live Inspection

```
POST /api/v1/live-inspect-frame       # Analyze JPEG frame
GET  /api/v1/live-inspect-proxy       # Capture and analyze
GET  /api/v1/camera/snapshot          # Capture camera frame
```

---

# 9. Quality Control Features

## 9.1 Human Review Queue

When the AI cannot confidently determine PASS/FAIL (e.g., anomaly score between thresholds), the seat is queued for human review.

**Flow:**
1. AI returns REVIEW outcome
2. Record added to review queue with annotated image
3. Inspector reviews and makes decision (PASS/REWORK/SCRAP)
4. Decision recorded and pallet released if PASS

## 9.2 Audit Sampling

Random sampling of PASS seats for quality auditor verification.

**Process:**
1. Quality manager requests sample (e.g., 5 seats)
2. System randomly selects PASS seats not previously sampled
3. Auditor inspects physical seat against "gold standard"
4. Records PASS/FAIL with discrepancy details

## 9.3 Shift Reports

End-of-shift comprehensive quality analysis:

- Total seats inspected
- Pass/Review/Fail rates
- Camera vs Inspector agreement
- Defect escape rate (AI missed)
- False reject rate (AI over-rejected)
- Top defect types (Pareto)

## 9.4 SPC (Statistical Process Control)

Real-time measurement tracking:

- **X-bar Charts**: Track mean values over time
- **Control Limits**: UCL/LCL calculation (3-sigma)
- **Cpk Analysis**: Process capability index
- **Violation Detection**: Measurements outside control limits

---

# 10. Configuration

## 10.1 System Configuration (`configs/system.yaml`)

```yaml
system:
  environment: "development"        # or "production"
  shadow_mode: false                # Enable shadow mode
  save_images: true                 # Save captured images
  image_retention_days: 30          # Days before cleanup

database:
  url: "sqlite:///./data/inspection.db"
  echo_sql: false

plc:
  adapter: "simulator"              # simulator/modbus/snap7/opcua
  host: "127.0.0.1"
  port: 502

storage:
  image_dir: "storage/images"
  raw_image_dir: "storage/images/raw"
  annotated_image_dir: "storage/images/annotated"
  defect_crops_dir: "storage/images/defects"

coordinator:
  expected_stations: ["STATION_1", "STATION_2", "STATION_3", "STATION_4"]
  cycle_timeout_s: 60.0
```

## 10.2 Station Configuration

Each station has its own YAML file in `configs/stations/`:
- `station_1_leather.yaml`
- `station_2_stitch.yaml`
- `station_3_plastic.yaml`
- `station_4_complete.yaml`

## 10.3 Variant Configuration

Variants define seat types in `configs/variants/`:
- `FRONT_LH_BLACK`
- `FRONT_RH_BLACK`
- `FRONT_LH_GREY`
- `REAR_BENCH_BLACK`

Each variant includes:
- Nominal values for measurements
- Component specifications
- Golden images directory
- Limit overrides

---

# 11. Safety and Interlocks

## 11.1 Label Printer Safety Interlock

The label printer is **strictly controlled**:

```
Label Printer Enable Conditions:
┌─────────────────────────────────────────────┐
│ 1. All 4 stations must report PASS          │
│ 2. Mechanism cycle test must PASS (Stn 4)  │
│ 3. Lock sensor must be CONFIRMED            │
│ 4. No missing stations                      │
└─────────────────────────────────────────────┘
              ↓ ALL TRUE ↓
     ┌─────────────────────────┐
     │ ENABLE LABEL PRINTER    │
     │ (for current seat only) │
     └─────────────────────────┘
```

## 11.2 Emergency Stop

- **Activation**: Immediate line stop, pallet hold, printer disable
- **Indicators**: Red on operator panel
- **Reset**: Manual reset required

## 11.3 Fail-Safe Behaviors

| Failure Scenario | System Response |
|-----------------|-----------------|
| Camera offline | FAIL, hold pallet |
| Capture failure | FAIL, hold pallet |
| Database write failure | FAIL, hold pallet |
| AI inference error | FAIL, hold pallet |
| PLC communication loss | FAIL, hold pallet |
| Missing station result | FAIL, hold pallet |
| Cycle timeout | Auto-FAIL seat |

## 11.4 Shadow Mode Safety

In shadow mode, all physical safety interlocks are bypassed:
- No PLC commands sent
- No pallet holds triggered
- No printer enable signals
- All decisions logged for later analysis

---

# Appendix A: Feature Summary Table

| Feature | Description | Location |
|---------|-------------|----------|
| Multi-Station Inspection | 4 stations covering full inspection | Stations 1-4 |
| Shadow Mode | Validation without physical output | System config |
| AI Inference | ONNX-based models | inference/ |
| Live Dashboard | Real-time monitoring | Frontend |
| Review Queue | Human-in-loop inspection | API endpoint |
| Audit Trail | Immutable logging | Database |
| SPC Charts | Statistical process control | Analytics |
| Defect Gallery | Browse detected defects | Dashboard |
| Shift Reports | End-of-shift analysis | Reports |
| Camera Management | Configure/manage cameras | API endpoint |
| ROI Editor | Define inspection regions | Dashboard |
| Variant Management | Multiple seat variants | configs/variants |
| Quality Auditor | Audit sampling | Dashboard |

---

# Appendix B: API Quick Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | System health check |
| `/api/v1/stations/result` | POST | Submit station result |
| `/api/v1/seats/{id}` | GET | Get seat status |
| `/api/v1/seats/{id}/export` | GET | Export seat trace |
| `/api/v1/reviews/pending` | GET | List pending reviews |
| `/api/v1/reviews/{id}/decision` | POST | Submit review decision |
| `/api/v1/dashboard/live` | GET | Live line view |
| `/api/v1/dashboard/quality-trends` | GET | Quality trends |
| `/api/v1/dashboard/defect-gallery` | GET | Defect gallery |
| `/api/v1/dashboard/shift-report` | GET | Shift report |
| `/api/v1/dashboard/system-health` | GET | System health |
| `/api/v1/audit` | GET | Audit log |
| `/api/v1/system/shadow-mode` | POST | Toggle shadow mode |
| `/api/v1/analytics/spc-measurements` | GET | SPC charts data |
| `/api/v1/cameras/detect` | GET | Detect cameras |
| `/api/v1/cameras/config` | GET/POST | Camera configuration |

---

# Appendix C: Database Schema

| Table | Purpose |
|-------|---------|
| `SeatInspectionRecord` | Overall seat inspection record |
| `StationResultRecord` | Per-station results |
| `CameraResultRecord` | Per-camera results |
| `DefectRecord` | Individual defect records |
| `HumanReviewRecord` | Review queue entries |
| `ShadowDecisionRecord` | Shadow mode decisions |
| `AuditSampleRecord` | Audit sampling records |
| `AuditLogRecord` | Immutable audit trail |

---

*Document Version: 1.0*
*Generated: October 2024*
*System Version: v0.1.0*