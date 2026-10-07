# OEM Vision Data Collection Checklist & Retraining Workflow

This procedure ensures every car seat variant has adequate, statistically valid reference data prior to model training or line commissioning.

## 1. Per-Variant Collection Requirements

Before any variant can be enabled on the production line:
- [ ] **Golden Image**: High-resolution, dust-free capture under final calibrated station lighting. Saved to `configs/variants/<VARIANT_ID>/golden_images/master_golden.png`.
- [ ] **Sample Size**: Minimum **200–300 good seats** captured under fixed final lighting across at least 2 distinct production shifts and lots.
- [ ] **Boundary & Defect Samples**: At least 10 real or boundary defect samples of each defect category:
  - Wrong hand part (LH on RH or RH on LH)
  - Missing component (missing lever, handle, screw, clip)
  - Flash burr (> 0.3 mm)
  - Color mismatch ($\Delta E > 3.0$)
  - Crack or short shot
  - Shield gap out-of-tolerance
- [ ] **Sidecar Metadata**: Every image must have an accompanying JSON sidecar containing:
  - Seat ID, Station ID, Variant ID, Lot ID, Timestamp, Exposure ($\mu s$), Gain ($dB$).

## 2. Hand-Safety Augmentation Rules (CRITICAL)

```
+---------------------------------------------------------------------------------+
| IMPORTANT: LH and RH seats/parts are mirror images.                             |
| ANY HORIZONTAL OR VERTICAL FLIP AUGMENTATION ON LH/RH PARTS IS PROHIBITED.      |
| A horizontal flip would convert an LH part to an RH part in the training data,  |
| completely blinding the classifier to wrong-hand assembly escapes.              |
+---------------------------------------------------------------------------------+
```
Permitted augmentations:
- Subtle brightness scaling ($\pm 10\%$)
- Sub-pixel to slight spatial translation ($\pm 5$ pixels)
- Copy-paste synthetic defect patches (cracks, stains) onto known good seats

## 3. Retraining Workflow Trigger

Trigger the retraining workflow whenever:
1. **Material Shift**: A new supplier lot introduces a new rexene grain texture, sheen, or leather dye batch.
2. **Thread Shift**: A thread supplier change causes subtle thread thickness or specular reflection changes.
3. **Plastics Tooling Shift**: A tooling mold overhaul or repair alters the parting line or texture finish.
4. **Drift Warning**: Station 6 / Dashboard reports sudden confidence drop over 50 consecutive cycles.

### Retraining Execution Steps:
1. Add new images to `data/captures/<STATION_ID>/<VARIANT_ID>/<LOT_ID>/`.
2. Run `DatasetPartitioner.split_by_seat` to maintain seat-level isolation without touching the frozen test set.
3. Retrain model, run evaluation against the frozen test set.
4. Verify that Recall $\ge 99.5\%$ and False Reject $\le 3.0\%$ before deploying new ONNX weights to `models/`.
