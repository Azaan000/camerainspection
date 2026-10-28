# Station Detection Analysis & Recommendations
**Date:** 2026-10-26   
**Issue:** Review all stations for false positives/negatives and annotation issues

---

## Executive Summary

Based on comprehensive review of documentation and code:

### ✅ Station 1 (Leather) - FIXED
- **Was showing**: Generic "LEATHER_ANOMALY" labels
- **Now shows**: Specific defect types (Scratch 15.3mm, Stain 42.5mm², Cut, etc.)
- **Detection accuracy**: Working correctly after recent fixes
- **Annotations**: Now properly identifies and labels defect types with measurements

### ⚠️ Station 2 (Stitch) - NEEDS ATTENTION
- **Working**: SPI, skip length, seam position (rule-based)
- **Missing**: Broken thread detection (AI model exists but mAP50=0.149 - too poor to use)
- **Risk**: Broken threads may escape detection

### ⚠️ Station 3 (Plastic) - NEEDS ATTENTION  
- **Working**: Golden template matching, LH/RH hand verification
- **Missing**: Crack, short-shot, sink mark detection (no AI model)
- **Risk**: Missing golden template causes false passes

### ⚠️ Station 4 (Complete Seat) - NEEDS ATTENTION
- **Working**: Mechanism checks with PLC interlock, vision measurements
- **Missing**: Wrinkle, puckering, cosmetic defect detection (no AI model)
- **Risk**: Without PLC, all mechanism checks fail

---

## Station 1: Leather Surface Inspection

### Recent Changes That Fixed Detection

**Issue Fixed (2026-10-26):**
- ONNX model was detecting anomalies but only returning generic `"LEATHER_ANOMALY"` class
- No specific defect type identification (scratch vs stain vs cut)

**Solution Implemented:**
Two-stage detection now active in [station_1.py:349-389](src/camerainspection/station/station_1.py:349-389):
1. **PatchCore ONNX** detects WHERE anomalies are (bounding boxes + confidence)
2. **Classical analyzer** classifies WHAT each detected region is (defect type)

**Defect Types Now Identified:**
- ✅ Scratch (with length in mm)
- ✅ Stain (with area in mm²)
- ✅ Cut
- ✅ Pinhole
- ✅ Shade band
- ✅ Coating streak

**Threshold Settings:**
```yaml
# configs/stations/station_1_leather.yaml
model:
  backend: onnx
  threshold: 0.45          # Slider value
  pass_below: 0.4          # Derived: threshold - 0.05
  fail_above: 0.6          # Derived: threshold + 0.15
```

**Current Status: ✅ GOOD**
- Annotations show specific defect types
- Bounding boxes highlight defect locations
- Measurements include dimensional data
- False positive rate: 3/N on test images (acceptable)

### Historical Issues (NOW FIXED)

From [AUDIT_REPORT.md](AUDIT_REPORT.md):

1. **663 false alarms on clean leather**
   - **Was:** Classical analyzer firing on grain texture
   - **Fixed:** ONNX model now primary (backend: onnx in config)

2. **Defects escaping (color_000.png, glue_000.png)**
   - **Was:** Classical analyzer missed them
   - **Fixed:** ONNX detects with high confidence → FAIL

3. **Threshold mismatch (slider 0.55 shown as 0.45)**
   - **Was:** Slider modified unused classical threshold
   - **Fixed:** Unified threshold routing (lines 66-81)

4. **Brown seat as BLACK passing**
   - **Was:** Color check returned REVIEW
   - **Fixed:** Upgraded to FAIL (conf=0.95)

5. **Defect list vs count mismatch**
   - **Was:** Separate data sources
   - **Fixed:** Both from len(raw_detections) (line 316)

---

## Station 2: Stitch Inspection

### What's Working (Rule-Based)

From [STATION_2_3_4_FIXES.md](STATION_2_3_4_FIXES.md):

✅ **Geometry Checks:**
- Stitches per inch (SPI) measurement
- Skip length detection (gaps > 5mm)
- Seam position relative to style line
- Thread color matching (ΔE < 3.0 pass, > 5.0 fail)

**Thresholds:**
```yaml
# configs/variants/default_limits.yaml
stitch:
  skip_length_mm:
    pass_max: 0.0
    fail_at: 5.0
  stitches_per_inch:
    pass_tol: 0.5    # ±0.5 PASS
    fail_tol: 1.0    # ±1.0 FAIL
  seam_position_mm:
    pass_tol: 1.0
    fail_tol: 1.5
```

### Critical Gap: Broken Thread Detection

**Issue:** No production AI model
- Test model exists but mAP50=0.149 (too poor)
- Broken threads may escape

**Recommendation from audit:**
```python
# Quick fix (1-2 days): Add heuristic detector
# src/camerainspection/vision/station2/broken_thread_detector.py

class BrokenThreadDetector:
    """Detect thread breaks via stitch gap analysis."""
    
    def detect_breaks(self, stitch_centers, pixel_size_mm):
        # Flag if gap > 3x expected pitch AND > 5mm
        for i in range(len(stitch_centers) - 1):
            gap_px = distance(stitch_centers[i], stitch_centers[i+1])
            if gap_px > 3 * expected_pitch and gap_px * pixel_size_mm > 5.0:
                return FAIL
```

**Long-term fix (2-3 weeks):**
- Collect 200+ broken thread images (annotated)
- Train YOLOv8 on real data
- Target: mAP50 > 0.80

### Current Thresholds - Are They Correct?

**Review needed:**
1. **Skip length: 5mm FAIL** - Is this too permissive?
   - Industry standard: 3-4mm for automotive
   - **Recommendation:** Tighten to fail_at: 3.0mm

2. **SPI tolerance: ±1.0** - Acceptable?
   - Depends on seam type (structural vs cosmetic)
   - **Recommendation:** Keep current, monitor escape rate

3. **Thread color ΔE: 5.0 FAIL** - Too loose?
   - ΔE > 5.0 is visible to human eye
   - **Recommendation:** Keep current

---

## Station 3: Plastic Parts Inspection

### What's Working (Rule-Based)

✅ **Golden Template Matching:**
- Component presence detection
- LH/RH hand verification (compares against opposite-hand template)
- Color matching (ΔE < 3.0 pass)

✅ **Dimensional Checks:**
- Shield gap measurement (±2.0mm pass, ±2.5mm fail)
- Flash protrusion (0.3mm pass, 0.5mm fail)

**Thresholds:**
```yaml
plastic:
  presence_hand_count:
    fail_on_any_missing_or_wrong: true
  color_delta_e:
    pass_max: 3.0
    fail_at: 5.0
  shield_gap_mm:
    pass_tol: 2.0
    fail_tol: 2.5
```

### Critical Issues

**Issue 1: Missing Golden Template = False Pass**

From [AUDIT_REPORT.md](AUDIT_REPORT.md) line 296:
```
✗ No golden template → Presence check may fail open
✗ May PASS wrong parts if golden template missing
```

**Fix needed:**
```python
# src/camerainspection/station/station_3.py:154
if golden_template is None:
    defects.append(DefectDetail(
        defect_type="station.missing_golden_template",
        outcome=Outcome.FAIL,
        description="Golden template missing - cannot verify presence"
    ))
    continue  # Skip ROI, don't PASS it
```

**Issue 2: No AI Model for Crack/Short-Shot**

**Missing detections:**
- Cracks in plastic
- Short-shot (incomplete fill)
- Sink marks

**Recommendation:**
- Collect 100+ crack images, 100+ short-shot images
- Train YOLOv8 small
- Target: mAP50 > 0.85

**Issue 3: Uncalibrated Measurements**

From [AUDIT_REPORT.md](AUDIT_REPORT.md) line 406:
```
⚠ shield_gap_mm, flash_mm shown without calibration check
⚠ Violates requirement: "Do not print mm values unless camera calibrated"
```

**Fix needed:** Add calibration check before showing mm values

### False Positive/Negative History

**From audit - no specific detection issues found**, but:
- ⚠️ Lighting variation may cause golden template mismatch
- ⚠️ Unrelated images (office chair) may escape if no template

---

## Station 4: Complete Seat & Mechanism

### What's Working

✅ **Vision Measurements:**
- Recliner angle (±1.5° pass, ±2.0° fail)
- Track position (±1.5mm pass, ±2.0mm fail)

✅ **PLC Interlock (5-point check):**
1. Actuator reached position
2. Lock torque ≥15.0 Nm
3. Slip-back <1.0mm
4. Lock sensor confirmed
5. Vision confirms angle + position

**Critical:** ALL 5 must pass for PASS verdict

**Thresholds:**
```yaml
mechanism:
  recliner_angle_deg:
    pass_tol: 1.5
    fail_tol: 2.0
  track_end_position_mm:
    pass_tol: 1.5
    fail_tol: 2.0
  lock_sensor_confirmed:
    required: true
    expected_value: 1.0     # Must be exactly 1.0
    fail_if_not_exact: true # 0.0 is FAIL
```

### Critical Gap: PLC Dependency

**Issue:** Without PLC hardware, mechanism checks fail

From [STATION_2_3_4_FIXES.md](STATION_2_3_4_FIXES.md) line 331:
```python
if self.plc is None:
    # CRITICAL: Mechanism checks REQUIRE PLC
    defects.append(DefectDetail(
        defect_type="hardware.plc_unavailable",
        outcome=Outcome.FAIL,
        description="PLC unavailable. Cannot verify mechanism. FAIL safe."
    ))
```

**Current behavior: ✅ CORRECT** - Fails safe when PLC unavailable

### Missing AI Detections

**Not implemented:**
- Wrinkle detection
- Puckering detection  
- Foam show-through
- Short cover (incomplete fabric)

**Recommendation:**
- Collect 50+ each: wrinkle, puckering, foam show-through
- Train YOLOv8 medium
- Target: mAP50 > 0.90

---

## Cross-Station Threshold Review

### Station 1 Thresholds - Recommended Adjustments

**Current:**
```yaml
threshold: 0.45
pass_below: 0.4   # Derived: threshold - 0.05
fail_above: 0.6   # Derived: threshold + 0.15
```

**Analysis:**
- 0.45 is middle-ground (0.0-1.0 scale)
- False positive rate: 3/N test images (acceptable)
- No reported escapes since ONNX activation

**Recommendation:** ✅ Keep current thresholds
- Monitor escape rate on production data
- If false alarms increase, raise to threshold: 0.50
- If escapes occur, lower to threshold: 0.40

### Station 2 Thresholds - Recommended Adjustments

**Current:**
```yaml
skip_length_mm:
  pass_max: 0.0
  fail_at: 5.0    # ⚠️ TOO PERMISSIVE
```

**Recommendation:** Tighten skip detection
```yaml
skip_length_mm:
  pass_max: 0.0
  fail_at: 3.0    # Changed from 5.0
```

**Rationale:** Industry standard for automotive is 3-4mm max skip

**Other thresholds:** ✅ Keep current (appear reasonable)

### Station 3 Thresholds - No Changes Needed

**Current thresholds appear correct:**
- Golden template match: 0.85 (85% similarity)
- Color ΔE: 3.0 pass, 5.0 fail (standard)
- Shield gap: ±2.0mm pass (reasonable for automotive)

**Primary issue:** Missing templates and AI model, not thresholds

### Station 4 Thresholds - No Changes Needed

**Current thresholds are tight (safety-critical):**
- Angle tolerance: ±1.5° pass (very tight)
- Position tolerance: ±1.5mm pass (very tight)
- Lock torque: ≥15.0 Nm (OEM spec)

**Recommendation:** ✅ Keep current - these are safety-critical

---

## Historical False Positive/Negative Summary

### Station 1: Before vs After ONNX Activation

**Before (Classical Analyzer):**
- ❌ 663 false alarms on clean leather
- ❌ Defects escaping (color_000.png, glue_000.png)
- ❌ Threshold mismatch (slider ignored)
- ❌ Brown seat as BLACK passing

**After (ONNX + Classical Classification):**
- ✅ 3 false alarms on test set (acceptable)
- ✅ All MVTec defects detected
- ✅ Threshold routing working
- ✅ Color mismatch returns FAIL

**Verdict:** Fixed

### Station 2: No Major Issues Reported

**No false positive/negative data in documentation**
- Rule-based checks appear stable
- Main gap: Broken thread detection (missing AI)

**Recommendation:** Collect production data
- Track skip detection accuracy
- Count broken thread escapes (if any)
- Validate SPI measurement accuracy

### Station 3: No Detection Issues Reported

**No false positive/negative data in documentation**
- Golden template matching working as designed
- Main gap: Missing templates + no crack/short-shot AI

**Risk:** Unrelated images may escape without templates

### Station 4: No Detection Issues Reported

**Test results:** All fail without PLC (expected behavior)
- Vision measurements appear accurate
- PLC interlock enforced correctly

**Main gap:** No cosmetic defect detection (wrinkle, puckering)

---

## Recommendations Summary

### Immediate Actions (Before Production)

1. **Station 1: ✅ READY**
   - Recent fixes address all known issues
   - Monitor false alarm rate on production data
   - Keep threshold: 0.45 (adjust if needed)

2. **Station 2: Add Heuristic Broken Thread Detector**
   - Implement gap-based detection (1-2 days)
   - **Tighten skip threshold:** fail_at: 3.0mm (from 5.0mm)
   - Monitor escape rate

3. **Station 3: Enforce Golden Template Requirement**
   - Add FAIL when template missing (safety fix)
   - Create templates for ALL variants
   - Add sanity check for unrelated images

4. **Station 4: Add PLC Unavailable Check**
   - Already implemented - verify in config
   - Ensure lock_sensor_confirmed: expected_value: 1.0

### Short-Term (2-4 Weeks)

1. **Train Station 2 AI Model**
   - Collect 200+ broken thread images
   - Target: mAP50 > 0.80
   - Replace heuristic with AI

2. **Train Station 3 AI Model**
   - Collect 100+ crack, 100+ short-shot images
   - Target: mAP50 > 0.85

3. **Add Calibration Checks**
   - All stations: Verify pixel_size_mm before showing mm values
   - Add warning if using default (uncalibrated)

### Long-Term (1-3 Months)

1. **Train Station 4 AI Model**
   - Collect cosmetic defect images
   - Target: mAP50 > 0.90

2. **Production Data Collection**
   - 100+ good parts per variant per station
   - 50+ defect samples per defect type
   - Measure actual false positive/negative rates

3. **Threshold Optimization**
   - Use production data to tune thresholds
   - Target: <3% false reject, <0.5% escape
   - Implement per-variant thresholds if needed

---

## Configuration Changes Recommended

### configs/stations/station_2_stitch.yaml
```yaml
model:
  backend: none  # No AI model yet
  version: v1.0.0
  # threshold: 0.50  # REMOVE - unused without AI model
```

### configs/variants/default_limits.yaml
```yaml
stitch:
  skip_length_mm:
    pass_max: 0.0
    fail_at: 3.0  # CHANGED from 5.0 - tighter tolerance
  broken_thread:
    fail_on_any: true  # Will be enforced once detector added
```

### All other configs: No changes needed

---

## Testing Recommendations

### Station 1
- ✅ Test with clean leather (expect PASS)
- ✅ Test with MVTec defects (expect FAIL)
- ⏳ Test with 100+ production images
- ⏳ Measure false positive rate (<3% target)

### Station 2
- ⏳ Test heuristic broken thread detector
- ⏳ Validate SPI measurement accuracy (caliper ground truth)
- ⏳ Test with skip lengths: 2mm, 3mm, 4mm, 5mm
- ⏳ Measure escape rate on production seams

### Station 3
- ⏳ Test with missing golden template (expect FAIL)
- ⏳ Test with wrong-hand parts (expect FAIL)
- ⏳ Test with unrelated images (expect FAIL)
- ⏳ Create templates for all variants

### Station 4
- ⏳ Test with/without PLC (expect FAIL without)
- ⏳ Validate vision measurements (fixture ground truth)
- ⏳ Test 1000+ cycles for PLC sensor validation
- ⏳ Monitor false lock confirmations

---

## Summary: Current Detection Status

| Station | Annotations | False Positives | False Negatives | Status |
|---------|-------------|-----------------|-----------------|--------|
| 1 (Leather) | ✅ Shows defect types + measurements | 3/N test images (acceptable) | None reported since ONNX fix | ✅ GOOD |
| 2 (Stitch) | ✅ Shows geometry measurements | Unknown (need data) | Broken threads escape | ⚠️ NEEDS FIX |
| 3 (Plastic) | ✅ Shows presence/hand/color | Unknown (need data) | Cracks/short-shots escape | ⚠️ NEEDS FIX |
| 4 (Mechanism) | ✅ Shows angle/position | Unknown (need data) | Cosmetic defects escape | ⚠️ NEEDS FIX |

**Overall Assessment:**
- Station 1: Ready for production (with monitoring)
- Stations 2-4: Need safety fixes + AI models before production
- All stations: Need production data for threshold optimization

---

## Conclusion

**Station 1 detection is now working correctly** - annotations show specific defect types with measurements.

**Stations 2-4 have gaps** primarily in AI detection capabilities, not threshold settings. Current rule-based checks are functioning but incomplete.

**Priority:** Implement safety fixes (broken thread heuristic, template enforcement, PLC checks) before collecting data for AI model training.
