# Automated Camera Inspection System for Car Seats

High-reliability automated vision inspection system for car seat manufacturing.

## Key Principles & Safety Invariants
1. **Strict Fail-Safe**: Any ambiguity (unrecognized barcode, unknown variant, disconnected camera/PLC, trigger timeout, corrupted frame) immediately yields `FAIL` or `REVIEW`. The PLC holds the pallet by default.
2. **Printer Interlock**: The OEM label printer output can **never** be enabled unless Station 1, 2, 3, 4 and the mechanism cycle test all register `PASS` AND the physical lock sensor is confirmed.
3. **No Hardcoded Values**: All thresholds, tolerances, nominals, and ROIs reside in YAML configs.
4. **Zero-Code Variant Expansion**: Adding a seat variant requires only a new configuration directory under `configs/variants/<VARIANT_ID>/` with optional limit overrides and golden images.

---

## Repository Structure (Phase 0)

```text
camerainspection/
├── configs/
│   ├── stations/            # Station 1 to 4 YAML configs (camera, light, ROI)
│   ├── variants/            # default_limits.yaml + variant directories
│   │   ├── FRONT_LH_BLACK/
│   │   ├── FRONT_RH_BLACK/
│   │   ├── REAR_BENCH_BLACK/
│   │   └── FRONT_LH_GREY/
│   └── system.yaml          # Database, coordinator, shadow mode flag
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml   # Multi-container setup (PostgreSQL + inspection service)
├── src/camerainspection/
│   ├── core/                # Models, exceptions, config loaders, LimitsEvaluator
│   ├── hardware/
│   │   ├── camera/          # BaseCamera, FolderReplayCamera, WebcamCamera, SyntheticCamera
│   │   └── plc/             # BasePLC, PLCSimulator (safety interlocks)
│   ├── inference/           # BaseInferenceEngine, MockInferenceEngine
│   ├── storage/             # SQLAlchemy DB manager & ORM models (SQLite/PostgreSQL)
│   └── station/             # BaseStation lifecycle engine
└── tests/
    ├── unit/                # Config, limits, camera, and PLC simulator tests
    └── integration/         # DB persistence and station lifecycle tests
```

---

## Quickstart & Testing

### 1. Run All Tests
```bash
pytest -v
```

### 2. Run Tests with Coverage
```bash
pytest -v --cov=camerainspection --cov-report=term-missing
```

### 3. Lint and Format Check
```bash
ruff check .
```

### 4. Run with Docker Compose (PostgreSQL)
```bash
docker compose -f docker/docker-compose.yml up --build
```
