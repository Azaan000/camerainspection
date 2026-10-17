---
name: visual-inspection-and-defect-gallery
description: Implementation of dual-pane live camera companion views, defect gallery image cards with SVG bounding box overlays, and high-resolution defect lightbox modal.
metadata:
  type: project
---

**Why:** The SeatGuard automotive car seat inspection system needed visual confirmation features so operators and engineers can view captured frames alongside the live camera feed and inspect defects visually in the gallery with bounding boxes and metrology readouts.
**How to apply:**
- Static file mounts (`/storage`, `/data`, `/configs`) serve captured frames, replay datasets, and golden master images from the repository root.
- The FastAPI backend joins `DefectRecord` with `StationResultRecord` in `/api/v1/dashboard/defect-gallery` and exposes active inspection snapshots and golden references via `/api/v1/dashboard/live-companion`.
- The frontend web UI (`ui/index.html`) includes a dual-pane live camera container with a 3-tab companion view (Latest Snapshot, Golden Reference, Station Filmstrip) and an enriched Defect Gallery with thumbnail previews, SVG bounding box overlays, and an interactive high-resolution Defect Lightbox Modal.
- All manual CLI commands, quickstart instructions, and tool scripts are fully documented in [[README.md]].
