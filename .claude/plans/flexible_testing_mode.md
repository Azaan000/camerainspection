# Plan: Flexible Testing Mode for Uncalibrated Injected Photos

## Context
When testing station inspection pipelines via the Web UI "Station Tester" (`/api/v1/stations/{station_id}/inject-image`), users frequently inject uncalibrated or arbitrarily resized photos (e.g. `640x640` or mobile camera crops). Because inspection services enforce strict physical calibration checks (pixel size mm, strict camera ROI bounding boxes, optical pitch expectations), uncalibrated photos fail with `station.insufficient_stitches` or `station.uncalibrated` even when the AI models detect defects correctly.

This plan introduces a **Flexible Testing Mode** option in the API and UI to allow uncalibrated/arbitrary image testing without failing on ROI out-of-bounds or calibration mismatches.

---

## Proposed Changes

1. **API Endpoint (`/api/v1/stations/{station_id}/inject-image`)**:
   - Add an optional query parameter `flexible_mode: bool = False`.
   - When `flexible_mode=True`, pass a flag or override to the station inspection service to:
     - Fallback or auto-scale ROI boxes to fit the injected image dimensions if out-of-bounds.
     - Bypass strict hardware/calibration enforcement (`calibration_manager` and `require_all_hardware`).
     - Suppress `station.insufficient_stitches` or `station.measurement_invalid` errors caused by arbitrary resolution mismatches, focusing on AI defect detection and general measurements.

2. **Station Services (`Station1Service` through `Station4Service` / `BaseStation`)**:
   - Support a `flexible_mode: bool = False` argument in `inspect_image()` / `_inspect_seam()`.
   - When `flexible_mode=True`:
     - If the configured ROI exceeds image bounds, clamp or auto-adjust ROI to cover the entire image or valid region.
     - Skip uncalibrated error injection.

3. **Frontend (`StationTester.tsx`)**:
   - Add a checkbox/toggle for **"Flexible Testing Mode (Bypass strict ROI/calibration bounds for uncalibrated uploads)"**.
   - Pass `flexible_mode=true` as a query parameter when calling `injectStationImage`.

---

## Verification Plan
1. Run pytest test suite to ensure existing regression tests pass.
2. Test injecting a 640×640 uncalibrated image into Station 2 with `flexible_mode=true` via API/UI and verify it returns AI defect results without `station.insufficient_stitches` failure.
