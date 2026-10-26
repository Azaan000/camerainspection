# UI Components - Camera Inspection Safety System

This directory contains user interface components for monitoring and visualizing safety checks in the camera inspection system.

## Components

### 1. Safety Dashboard (`safety_dashboard.py`)

**Purpose:** Real-time web-based monitoring dashboard for all station safety checks.

**Features:**
- System-wide KPI metrics (active stations, failing checks, escape rates)
- Per-station safety status cards
- Color-coded status indicators (🟢 PASS, 🔴 FAIL, 🟡 REVIEW, ⚫ DISABLED)
- Expandable detail views for each safety check
- Inspection statistics and timestamps

**Technology:** Streamlit

**Running the Dashboard:**
```bash
# Install streamlit if not already installed
pip install streamlit

# Run the dashboard
streamlit run ui/safety_dashboard.py
```

**Development Mode:**
```bash
# Auto-reload on file changes
streamlit run ui/safety_dashboard.py --server.runOnSave true
```

**Configuration:**
The dashboard currently uses mock data in `get_mock_data()`. To connect to live data:

1. Replace `get_mock_data()` with a data connector to your inspection results database
2. Update the `main()` function to poll for new data
3. Consider adding WebSocket support for real-time updates

**Screenshot:**
```
╔══════════════════════════════════════════════════════════════════╗
║ 🔒 Camera Inspection System - Safety Dashboard                  ║
║ Updated: 2026-10-26 21:11:12                                     ║
╠══════════════════════════════════════════════════════════════════╣
║ Active Stations: 4/4  │ Failing Checks: 0  │ Review: 1  │ ... ║
╠══════════════════════════════════════════════════════════════════╣
║ STATION_2: Stitch Inspection                    [ENABLED] 0.42% ║
║                                                                   ║
║ #### Critical Safety Checks                                      ║
║ 🟢 Measurement Range Validation                                  ║
║    Status: PASS                                                  ║
║    Description: SPI in range 1-20, stitch count ≥ 3             ║
║ 🟢 Broken Thread Detector                                        ║
║    Status: PASS                                                  ║
║    Description: Heuristic gap detection (>3x pitch, >5mm)        ║
╚══════════════════════════════════════════════════════════════════╝
```

---

### 2. Safety Overlay (`safety_overlay.py`)

**Purpose:** Annotate inspection images with safety check results and defect highlights.

**Features:**
- Status banner with station ID, overall result, and timestamp
- Safety checks panel (right side) showing all check statuses
- Defect bounding boxes with labels
- Structured JSON safety report generation
- Categorizes defects by type (safety, quality, calibration)

**Usage Example:**

```python
from ui.safety_overlay import SafetyOverlay, generate_safety_report
import cv2

# Load inspection image
image = cv2.imread("path/to/inspection/image.jpg")

# Define safety checks
safety_checks = [
    {
        "name": "PLC Availability",
        "status": "PASS",
        "description": "PLC hardware connected",
    },
    {
        "name": "Camera Calibration",
        "status": "REVIEW",
        "description": "Camera uncalibrated - reporting pixels",
    },
]

# Define defects (optional)
defects = [
    {
        "defect_type": "mechanism.insufficient_torque",
        "outcome": "FAIL",
        "bounding_box": {"x": 100, "y": 200, "w": 50, "h": 50},
    }
]

# Create annotated image
annotated = SafetyOverlay.create_annotated_image(
    image=image,
    station_id="STATION_4",
    overall_status="FAIL",
    safety_checks=safety_checks,
    defects=defects,
)

# Save annotated image
cv2.imwrite("annotated_result.jpg", annotated)

# Generate JSON safety report
report = generate_safety_report(
    station_id="STATION_4",
    inspection_result={
        "defects": defects,
        "measurements": {"lock_sensor_confirmed": 0.0},
    },
    output_path="safety_report.json",
)
```

**Report Structure:**
```json
{
  "station_id": "STATION_4",
  "timestamp": "2026-10-26T21:11:12",
  "overall_status": "FAIL",
  "summary": {
    "total_defects": 1,
    "safety_defects": 1,
    "quality_defects": 0,
    "calibration_issues": 0
  },
  "safety_checks": {
    "hardware_available": true,
    "calibrated": true,
    "golden_templates_loaded": true,
    "measurements_valid": true
  },
  "defects": {
    "safety": [...],
    "quality": [...],
    "calibration": [...]
  }
}
```

---

## Integration Guide

### Adding to Production System

1. **Dashboard Integration:**
   ```python
   # In your main application
   from ui.safety_dashboard import create_safety_dashboard, StationStatus, SafetyCheck
   
   # Collect station data
   stations = [
       StationStatus(
           station_id="STATION_2",
           station_name="Stitch Inspection",
           enabled=True,
           safety_checks=[...],
           escape_rate=0.0042,
       ),
       # ... more stations
   ]
   
   # Launch dashboard
   create_safety_dashboard(stations)
   ```

2. **Image Annotation Integration:**
   ```python
   # After inspection completes
   from ui.safety_overlay import SafetyOverlay
   
   annotated_image = SafetyOverlay.create_annotated_image(
       image=original_image,
       station_id=station_id,
       overall_status=determine_overall_status(defects),
       safety_checks=extract_safety_checks(measurements, defects),
       defects=defects,
   )
   
   # Save for review/archive
   save_inspection_result(annotated_image, inspection_id)
   ```

3. **Report Generation:**
   ```python
   # Generate report after each inspection
   report = generate_safety_report(
       station_id=station_id,
       inspection_result={
           "defects": defects,
           "measurements": measurements,
       },
       output_path=f"reports/{inspection_id}.json",
   )
   
   # Upload to database/archive
   store_safety_report(report)
   ```

---

## Customization

### Dashboard Styling
Edit `safety_dashboard.py`:
- Modify `render_safety_badge()` for different status icons
- Adjust `render_station_card()` layout
- Change KPI thresholds in `create_safety_dashboard()`

### Overlay Colors
Edit `safety_overlay.py`:
- Modify `SafetyOverlay.COLOR_*` constants (BGR format)
- Adjust font sizes in `cv2.putText()` calls
- Change panel positioning in `draw_safety_checks()`

### Adding New Safety Checks
1. Add check to station inspection logic
2. Include in defects list with appropriate type
3. Dashboard automatically picks up new defect types
4. Overlay categorizes by prefix (hardware.*, station.*, camera.*)

---

## Dependencies

```bash
pip install streamlit opencv-python numpy
```

For development:
```bash
pip install streamlit opencv-python numpy black pytest
```

---

## Testing

```python
# Test overlay rendering
python -c "from ui.safety_overlay import SafetyOverlay; print('✓ Overlay loaded')"

# Test dashboard (opens in browser)
streamlit run ui/safety_dashboard.py
```

---

## Troubleshooting

**Dashboard won't start:**
- Check if port 8501 is available
- Run with different port: `streamlit run ui/safety_dashboard.py --server.port 8502`

**Images not displaying:**
- Verify OpenCV is installed: `python -c "import cv2; print(cv2.__version__)"`
- Check image paths are absolute or relative to script location

**Colors look wrong:**
- OpenCV uses BGR format, not RGB
- Verify color constants in `SafetyOverlay` class

---

## Future Enhancements

- [ ] WebSocket support for live updates
- [ ] Historical trend charts
- [ ] Defect heatmaps by location
- [ ] Mobile-responsive layout
- [ ] Email alerts for critical failures
- [ ] Export reports to PDF
- [ ] Dark/light theme toggle

---

## License

Copyright © 2026 - Internal use only
