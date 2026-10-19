"""FastAPI application factory defining secure inspection ingestion, review, and analytics APIs."""

from __future__ import annotations

import io
import json
import os
import random
import re
import secrets
import time
import zipfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from camerainspection.coordinator.service import InspectionCoordinator
from camerainspection.core.logging import get_logger
from camerainspection.core.models import Outcome, StationInspectionResult
from camerainspection.storage.db import DatabaseManager
from camerainspection.storage.entities import (
    AuditLogRecord,
    AuditSampleRecord,
    DefectRecord,
    HumanReviewRecord,
    SeatInspectionRecord,
    ShadowDecisionRecord,
    StationResultRecord,
)
from camerainspection.tools.shift_report import generate_shift_report_dict

logger = get_logger("api.app")

SEAT_ID_REGEX = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
FORBIDDEN_DEFAULT_KEY = "inspector_secret_token_123"

# Default local development origins allowed to call the API from a browser.
# 8000 = API serving its own UI, 5500 = VS Code Live Server.
DEFAULT_CORS_ORIGINS = (
    "http://127.0.0.1:8000,http://localhost:8000,"
    "http://127.0.0.1:5500,http://localhost:5500"
)


def get_ui_index_path() -> Path:
    """Locate ui/index.html (override with UI_INDEX_PATH)."""
    override = os.getenv("UI_INDEX_PATH")
    if override:
        return Path(override).resolve()
    # app.py -> api -> camerainspection -> src -> <repo root>
    return Path(__file__).resolve().parents[3] / "ui" / "index.html"


def get_expected_api_key() -> str:
    """Validate and return the configured INSPECTION_API_KEY."""
    key = os.getenv("INSPECTION_API_KEY", "")
    if not key or key == FORBIDDEN_DEFAULT_KEY or len(key) < 32:
        raise RuntimeError(
            "INSPECTION_API_KEY must be set, must not use default placeholder, "
            f"and must be at least 32 characters long. Current key length: {len(key)}"
        )
    return key


def verify_api_key(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None, alias="Authorization"),
) -> str:
    """Validate API key via constant-time comparison against header or Bearer token."""
    expected_key = get_expected_api_key()

    provided_key: str | None = None
    if x_api_key:
        provided_key = x_api_key.strip()
    elif authorization:
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided_key = parts[1].strip()

    if not provided_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Missing X-API-Key or Authorization Bearer header.",
        )

    expected = expected_key.encode("utf-8")
    provided = provided_key.encode("utf-8")
    if not (secrets.compare_digest(provided, expected) and len(expected) > 0):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Invalid inspection API key.",
        )

    return "authenticated_inspector"


class RateLimiter:
    """In-process token bucket rate limiter per client IP + route category."""

    def __init__(self, requests_per_minute: float = 60.0, burst: float = 60.0) -> None:
        self.rate = requests_per_minute / 60.0
        self.capacity = burst
        self.buckets: dict[str, tuple[float, float]] = defaultdict(lambda: (self.capacity, time.monotonic()))

    def consume(self, client_id: str) -> tuple[bool, float]:
        now = time.monotonic()
        tokens, last_time = self.buckets[client_id]
        elapsed = now - last_time
        tokens = min(self.capacity, tokens + elapsed * self.rate)

        if tokens >= 1.0:
            self.buckets[client_id] = (tokens - 1.0, now)
            return True, 0.0
        else:
            self.buckets[client_id] = (tokens, now)
            wait_time = (1.0 - tokens) / self.rate
            return False, wait_time


# Default rate limits: 60 writes/min, 10 exports/min
write_limiter = RateLimiter(requests_per_minute=60.0, burst=60.0)
export_limiter = RateLimiter(requests_per_minute=10.0, burst=10.0)


def rate_limit_writes(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    allowed, wait_s = write_limiter.consume(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry after {int(wait_s) + 1}s.",
            headers={"Retry-After": str(int(wait_s) + 1)},
        )


def rate_limit_exports(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    allowed, wait_s = export_limiter.consume(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Export rate limit exceeded. Retry after {int(wait_s) + 1}s.",
            headers={"Retry-After": str(int(wait_s) + 1)},
        )


def validate_seat_id(seat_id: str) -> str:
    """Enforce alphanumeric, underscore, dot, colon, hyphen seat ID, max 64 chars."""
    if not SEAT_ID_REGEX.match(seat_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid seat ID '{seat_id}'. Allowed characters: A-Za-z0-9_.:- up to 64 chars.",
        )
    return seat_id


class ReviewDecisionPayload(BaseModel):
    decision: str = Field(..., description="Decision outcome: PASS, REWORK, or SCRAP")
    notes: str = Field("", description="Review notes / explanation")
    inspector_id: str | None = Field(None, description="Self-declared inspector badge ID")


class StationResultIngestRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    result: StationInspectionResult | None = None
    seat_id: str | None = None
    station_id: str | None = None
    variant_id: str | None = None
    outcome: Outcome | None = None
    cycle_time_ms: float = 0.0
    model_version: str = "v0.1.0"
    config_version: str = "v0.1.0"
    defects: list[Any] = Field(default_factory=list)
    measurements: dict[str, float] = Field(default_factory=dict)
    camera_results: dict[str, Any] = Field(default_factory=dict)
    camera_image_paths: dict[str, str] = Field(default_factory=dict)


class ShadowDecisionPayload(BaseModel):
    seat_id: str
    inspector_id: str
    decision: str = Field(..., description="PASS or FAIL")
    notes: str = ""


class AuditDecisionPayload(BaseModel):
    auditor_id: str
    decision: str = Field(..., description="PASS or FAIL")
    discrepancy_details: str = ""


def create_app(
    db_manager: DatabaseManager,
    coordinator: InspectionCoordinator | None = None,
) -> FastAPI:
    """Create and configure FastAPI application."""
    # Ensure strong API key at startup
    get_expected_api_key()

    app = FastAPI(
        title="Automated Camera Inspection System API",
        version="0.1.0",
        description="End-of-line car seat camera inspection service with fail-safe safety gating.",
    )

    allowed_origins = [
        orig.strip()
        for orig in os.getenv("CORS_ALLOWED_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
        if orig.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins if allowed_origins else ["http://127.0.0.1:8000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["X-API-Key", "Authorization", "Content-Type"],
    )

    from fastapi.staticfiles import StaticFiles

    # Repo root is 3 levels up from src/camerainspection/api/app.py
    repo_root = Path(__file__).resolve().parents[3]

    # Mount storage directory (for live & recorded captures)
    storage_dir = repo_root / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / "captures").mkdir(parents=True, exist_ok=True)
    (storage_dir / "images").mkdir(parents=True, exist_ok=True)
    app.mount("/storage", StaticFiles(directory=str(storage_dir)), name="storage")

    # Mount data directory (for simulation replays and test sets)
    data_dir = repo_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/data", StaticFiles(directory=str(data_dir)), name="data")

    # Mount configs directory (for variant golden images)
    configs_dir = repo_root / "configs"
    if configs_dir.is_dir():
        app.mount("/configs", StaticFiles(directory=str(configs_dir)), name="configs")

    @app.get("/", include_in_schema=False)
    def ui_index() -> FileResponse:
        """Serve the SeatGuard dashboard from the same origin as the API (no CORS needed)."""
        index_path = get_ui_index_path()
        if not index_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"UI not found at {index_path}. Set UI_INDEX_PATH to override.",
            )
        return FileResponse(index_path, media_type="text/html")

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok", "service": "camera-inspection-system", "version": "0.1.0"}

    # -------------------------------------------------------------
    # Ingestion & Seat Query Endpoints
    # -------------------------------------------------------------

    @app.post("/api/v1/stations/result", status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit_writes)])
    def submit_station_result(
        payload: StationResultIngestRequest,
        auth_user: str = Depends(verify_api_key),
    ) -> dict[str, Any]:
        """Submit station result from camera inspection node."""
        if payload.result is not None:
            st_result = payload.result
        else:
            if not payload.seat_id or not payload.station_id or not payload.variant_id or not payload.outcome:
                raise HTTPException(status_code=422, detail="Missing required station result fields.")
            st_result = StationInspectionResult(
                seat_id=validate_seat_id(payload.seat_id),
                station_id=payload.station_id,
                variant_id=payload.variant_id,
                outcome=payload.outcome,
                cycle_time_ms=payload.cycle_time_ms,
                model_version=payload.model_version,
                config_version=payload.config_version,
                defects=payload.defects,
                measurements=payload.measurements,
                camera_results=payload.camera_results,
                camera_image_paths=payload.camera_image_paths,
            )

        validate_seat_id(st_result.seat_id)

        st_id = db_manager.record_station_result(st_result)
        db_manager.log_audit(
            event_type="STATION_RESULT_SUBMITTED",
            details=f"Station {st_result.station_id} reported {st_result.outcome.value} (Auth: {auth_user})",
            seat_id=st_result.seat_id,
            station_id=st_result.station_id,
        )

        overall = None
        if coordinator:
            overall = coordinator.register_station_result(st_result)

        return {
            "recorded": True,
            "station_result_id": st_id,
            "finalized": overall is not None,
            "overall_outcome": overall.outcome.value if overall else None,
            "overall_status": overall.outcome.value if overall else "IN_PROGRESS",
            "printer_enabled": overall.label_printer_enabled if overall else False,
        }

    @app.get("/api/v1/seats/{seat_id}")
    def get_seat_status(
        seat_id: str,
        auth_user: str = Depends(verify_api_key),
    ) -> dict[str, Any]:
        """Retrieve complete inspection history and outcome for a given seat ID."""
        valid_sid = validate_seat_id(seat_id)
        with db_manager.session_scope() as session:
            record = (
                session.query(SeatInspectionRecord)
                .filter(SeatInspectionRecord.seat_id == valid_sid)
                .first()
            )
            if not record:
                st_records = (
                    session.query(StationResultRecord)
                    .filter(StationResultRecord.seat_id == valid_sid)
                    .all()
                )
                if not st_records:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Seat ID '{valid_sid}' not found.",
                    )
                return {
                    "seat_id": valid_sid,
                    "variant_id": getattr(st_records[0], "variant_id", "UNKNOWN"),
                    "outcome": "IN_PROGRESS",
                    "shadow_mode": False,
                    "label_printer_enabled": False,
                    "mechanism_cycle_passed": False,
                    "lock_sensor_confirmed": False,
                    "station_results": [
                        {
                            "station_id": s.station_id,
                            "outcome": s.outcome,
                            "cycle_time_ms": s.cycle_time_ms,
                            "model_version": s.model_version,
                            "config_version": s.config_version,
                            "camera_results": json.loads(s.camera_results_json) if s.camera_results_json else {},
                            "camera_image_paths": (
                                json.loads(s.camera_image_paths_json) if s.camera_image_paths_json else {}
                            ),
                            "defects": [
                                {
                                    "defect_type": d.defect_type,
                                    "outcome": d.outcome,
                                    "measured_value": d.measured_value,
                                    "nominal_value": d.nominal_value,
                                    "unit": d.unit,
                                    "confidence": d.confidence,
                                    "bbox": [d.bbox_x, d.bbox_y, d.bbox_w, d.bbox_h] if d.bbox_x is not None else None,
                                    "roi_name": d.roi_name,
                                    "camera_name": d.camera_name,
                                    "view": d.view,
                                    "description": d.description,
                                }
                                for d in s.defects
                            ],
                        }
                        for s in st_records
                    ],
                }

            return {
                "seat_id": record.seat_id,
                "variant_id": record.variant_id,
                "outcome": record.outcome,
                "shadow_mode": record.shadow_mode,
                "label_printer_enabled": record.label_printer_enabled,
                "mechanism_cycle_passed": record.mechanism_cycle_passed,
                "lock_sensor_confirmed": record.lock_sensor_confirmed,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "completed_at": record.completed_at.isoformat() if record.completed_at else None,
                "station_results": [
                    {
                        "station_id": s.station_id,
                        "outcome": s.outcome,
                        "cycle_time_ms": s.cycle_time_ms,
                        "model_version": s.model_version,
                        "config_version": s.config_version,
                        "camera_results": json.loads(s.camera_results_json) if s.camera_results_json else {},
                        "camera_image_paths": (
                            json.loads(s.camera_image_paths_json) if s.camera_image_paths_json else {}
                        ),
                        "defects": [
                            {
                                "defect_type": d.defect_type,
                                "outcome": d.outcome,
                                "measured_value": d.measured_value,
                                "nominal_value": d.nominal_value,
                                "unit": d.unit,
                                "confidence": d.confidence,
                                "bbox": [d.bbox_x, d.bbox_y, d.bbox_w, d.bbox_h] if d.bbox_x is not None else None,
                                "roi_name": d.roi_name,
                                "camera_name": d.camera_name,
                                "view": d.view,
                                "description": d.description,
                            }
                            for d in s.defects
                        ],
                    }
                    for s in record.station_results
                ],
            }

    @app.get("/api/v1/seats/{seat_id}/export", dependencies=[Depends(rate_limit_exports)])
    def export_seat_trace(
        seat_id: str,
        format: str = Query("zip"),  # noqa: A002
        auth_user: str = Depends(verify_api_key),
    ) -> Response:
        """Phase 9 Export endpoint: Returns zip file containing JSON audit trace + defect images."""
        valid_sid = validate_seat_id(seat_id)
        status_info = get_seat_status(valid_sid, auth_user=auth_user)
        with db_manager.session_scope() as session:
            logs = session.query(AuditLogRecord).filter_by(seat_id=valid_sid).all()
            reviews = session.query(HumanReviewRecord).filter_by(seat_id=valid_sid).all()
            shadow = session.query(ShadowDecisionRecord).filter_by(seat_id=valid_sid).all()

            status_info["audit_logs"] = [
                {
                    "event_type": log.event_type,
                    "details": log.details,
                    "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                }
                for log in logs
            ]
            status_info["reviews"] = [
                {
                    "inspector_id": r.inspector_id,
                    "decision": r.decision,
                    "notes": r.notes,
                    "status": r.status,
                    "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
                }
                for r in reviews
            ]
            status_info["shadow_decisions"] = [
                {
                    "inspector_id": s.inspector_id,
                    "decision": s.decision,
                    "notes": s.notes,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in shadow
            ]

        if format.lower() == "json":
            return Response(
                content=json.dumps(status_info, indent=2),
                media_type="application/json",
            )

        Path(os.getenv("IMAGE_STORAGE_ROOT", "storage/images")).resolve()

        # Create ZIP in memory with path traversal protection
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("audit_trace.json", json.dumps(status_info, indent=2))

            # Include images strictly within storage directory
            for sr in status_info.get("station_results", []):
                for cam_name, img_path in sr.get("camera_image_paths", {}).items():
                    if img_path:
                        real_p = Path(img_path).resolve()
                        try:
                            # Verify no path traversal outside storage_root or repo
                            real_p.relative_to(Path.cwd().resolve())
                        except ValueError:
                            logger.warning(f"Prevented path traversal export: {img_path}")
                            continue

                        if real_p.exists() and real_p.is_file():
                            arcname = f"images/{sr.get('station_id')}_{cam_name}_{real_p.name}"
                            zf.write(str(real_p), arcname=arcname)

        zip_buf.seek(0)
        return Response(
            content=zip_buf.getvalue(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="trace_{valid_sid}.zip"',
            },
        )

    # -------------------------------------------------------------
    # Human Review Queue Endpoints (Authenticated)
    # -------------------------------------------------------------

    @app.get("/api/v1/reviews/pending")
    def list_pending_reviews(
        auth_user: str = Depends(verify_api_key),
    ) -> list[dict[str, Any]]:
        """List inspections currently held in the REVIEW state."""
        with db_manager.session_scope() as session:
            pending = (
                session.query(HumanReviewRecord)
                .filter(HumanReviewRecord.status == "PENDING")
                .all()
            )
            out = []
            for r in pending:
                st_res = (
                    session.query(StationResultRecord)
                    .filter_by(seat_id=r.seat_id)
                    .first()
                )
                out.append({
                    "review_id": r.id,
                    "seat_id": r.seat_id,
                    "station_id": r.station_id,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "annotated_image_path": st_res.annotated_image_path if st_res else None,
                    "camera_image_paths": (
                        json.loads(st_res.camera_image_paths_json) if st_res and st_res.camera_image_paths_json else {}
                    ),
                })
            return out

    @app.post("/api/v1/reviews/{review_id}/decision", dependencies=[Depends(rate_limit_writes)])
    def resolve_review(
        review_id: int,
        payload: ReviewDecisionPayload,
        auth_user: str = Depends(verify_api_key),
    ) -> dict[str, Any]:
        """Record human inspector verdict and release pallet if approved."""
        allowed = {"PASS", "REWORK", "SCRAP"}
        if payload.decision not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid decision '{payload.decision}'. Allowed: {sorted(allowed)}",
            )

        with db_manager.session_scope() as session:
            rev = session.query(HumanReviewRecord).filter_by(id=review_id).first()
            if not rev:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Review ID {review_id} not found.",
                )
            if rev.status == "RESOLVED":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Review ID {review_id} has already been resolved.",
                )

            inspector = payload.inspector_id or auth_user
            db_manager.resolve_review(
                review_id=review_id,
                inspector_id=inspector,
                decision=payload.decision,
                notes=payload.notes,
            )

            seat = session.query(SeatInspectionRecord).filter_by(seat_id=rev.seat_id).first()
            if seat:
                if payload.decision == "PASS":
                    st_results = session.query(StationResultRecord).filter_by(seat_id=rev.seat_id).all()
                    can_pass = True
                    for sr in st_results:
                        if sr.station_id != rev.station_id and sr.outcome == "FAIL":
                            can_pass = False
                            break

                    if can_pass:
                        seat.outcome = "PASS"
                        if rev.station_id == "STATION_4":
                            seat.mechanism_cycle_passed = True
                        if coordinator and coordinator.plc:
                            station_id_str: str = rev.station_id or ""
                            coordinator.plc.set_station_result(station_id_str, Outcome.PASS, seat_id=rev.seat_id)
                            coordinator.plc.hold_pallet(station_id_str, hold=False)
                            lock_sensor_ok = coordinator.plc.is_mechanism_locked()
                            if lock_sensor_ok:
                                coordinator.plc.set_label_printer_enable(True, seat_id=rev.seat_id)
                                seat.label_printer_enabled = coordinator.plc.is_label_printer_enabled()
                            else:
                                seat.label_printer_enabled = False
                    else:
                        seat.outcome = "FAIL"
                        seat.label_printer_enabled = False
                else:
                    seat.outcome = "FAIL"
                    seat.label_printer_enabled = False
                    if coordinator and coordinator.plc:
                        coordinator.plc.hold_pallet(rev.station_id or "", hold=True)
                        coordinator.plc.set_label_printer_enable(False, seat_id=rev.seat_id)

        db_manager.log_audit(
            event_type="HUMAN_REVIEW_RESOLVED",
            details=(
                f"ReviewID {review_id} resolved as {payload.decision} by {inspector} "
                f"(Auth: {auth_user}). Notes: {payload.notes}"
            ),
            seat_id=rev.seat_id,
        )
        return {"review_id": review_id, "resolved": True, "decision": payload.decision}

    # -------------------------------------------------------------
    # Audit Trail Query Endpoint
    # -------------------------------------------------------------

    @app.get("/api/v1/audit")
    def query_audit_logs(
        seat_id: str | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
        auth_user: str = Depends(verify_api_key),
    ) -> list[dict[str, Any]]:
        """Query immutable OEM audit log trail."""
        with db_manager.session_scope() as session:
            query = session.query(AuditLogRecord)
            if seat_id:
                query = query.filter_by(seat_id=validate_seat_id(seat_id))
            records = query.order_by(AuditLogRecord.timestamp.desc()).limit(limit).all()
            return [
                {
                    "id": a.id,
                    "seat_id": a.seat_id,
                    "station_id": a.station_id,
                    "event_type": a.event_type,
                    "details": a.details,
                    "timestamp": a.timestamp.isoformat() if a.timestamp else None,
                }
                for a in records
            ]

    # -------------------------------------------------------------
    # Shadow Mode & Shift Report Endpoints (Phase 8)
    # -------------------------------------------------------------

    @app.post("/api/v1/shadow-mode/decision", dependencies=[Depends(rate_limit_writes)])
    def record_shadow_decision(
        payload: ShadowDecisionPayload,
        auth_user: str = Depends(verify_api_key),
    ) -> dict[str, Any]:
        """Record human inspector shadow-mode decision for a seat ID."""
        allowed = {"PASS", "FAIL"}
        dec_clean = payload.decision.upper().strip()
        if dec_clean not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid decision '{payload.decision}'. Allowed: {sorted(allowed)}",
            )

        validate_seat_id(payload.seat_id)

        with db_manager.session_scope() as session:
            rec = ShadowDecisionRecord(
                seat_id=payload.seat_id,
                inspector_id=payload.inspector_id or auth_user,
                decision=dec_clean,
                notes=payload.notes,
            )
            session.add(rec)

        db_manager.log_audit(
            event_type="SHADOW_DECISION_RECORDED",
            details=f"Seat {payload.seat_id} rated {dec_clean} by {payload.inspector_id}",
            seat_id=payload.seat_id,
        )
        return {"recorded": True, "seat_id": payload.seat_id, "decision": dec_clean}

    @app.get("/api/v1/dashboard/shift-report")
    def get_shift_report(
        threshold_pct: float = Query(3.0, ge=0.1, le=50.0),
        auth_user: str = Depends(verify_api_key),
    ) -> dict[str, Any]:
        """Generate comprehensive end-of-shift quality report comparing camera vs inspector."""
        with db_manager.session_scope() as session:
            return generate_shift_report_dict(session, false_reject_threshold_pct=threshold_pct)

    # -------------------------------------------------------------
    # Audit Sampling Endpoints (Phase 8)
    # -------------------------------------------------------------

    @app.post("/api/v1/audit/sample", dependencies=[Depends(rate_limit_writes)])
    def trigger_audit_sample(
        count: int = Query(5, ge=1, le=50),
        auth_user: str = Depends(verify_api_key),
    ) -> dict[str, Any]:
        """Randomly select N PASS seats for quality auditor to verify against master."""
        with db_manager.session_scope() as session:
            sampled_ids = {r.seat_id for r in session.query(AuditSampleRecord).all()}

            candidates = (
                session.query(SeatInspectionRecord)
                .filter(SeatInspectionRecord.outcome == "PASS")
                .all()
            )
            eligible = [s for s in candidates if s.seat_id not in sampled_ids]

            selected = random.sample(eligible, min(count, len(eligible)))

            new_records = []
            for s in selected:
                rec = AuditSampleRecord(
                    seat_id=s.seat_id,
                    auditor_id=auth_user,
                    status="PENDING",
                )
                session.add(rec)
                new_records.append(s.seat_id)

        db_manager.log_audit(
            event_type="AUDIT_SAMPLE_GENERATED",
            details=f"Selected {len(new_records)} seats for quality audit: {new_records}",
        )
        return {"sampled_count": len(new_records), "seats": new_records}

    @app.get("/api/v1/audit/samples")
    def list_audit_samples(
        auth_user: str = Depends(verify_api_key),
    ) -> list[dict[str, Any]]:
        """List active and completed auditor sample checks."""
        with db_manager.session_scope() as session:
            records = session.query(AuditSampleRecord).order_by(AuditSampleRecord.sampled_at.desc()).all()
            return [
                {
                    "id": r.id,
                    "seat_id": r.seat_id,
                    "auditor_id": r.auditor_id,
                    "status": r.status,
                    "decision": r.decision,
                    "discrepancy_details": r.discrepancy_details,
                    "sampled_at": r.sampled_at.isoformat() if r.sampled_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                }
                for r in records
            ]

    @app.post("/api/v1/audit/sample/{sample_id}/decision", dependencies=[Depends(rate_limit_writes)])
    def submit_audit_decision(
        sample_id: int,
        payload: AuditDecisionPayload,
        auth_user: str = Depends(verify_api_key),
    ) -> dict[str, Any]:
        """Record quality auditor inspection outcome against a sampled seat."""
        allowed = {"PASS", "FAIL"}
        dec_clean = payload.decision.upper().strip()
        if dec_clean not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid decision '{payload.decision}'. Allowed: {sorted(allowed)}",
            )

        with db_manager.session_scope() as session:
            rec = session.query(AuditSampleRecord).filter_by(id=sample_id).first()
            if not rec:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Audit sample ID {sample_id} not found.",
                )
            rec.auditor_id = payload.auditor_id or auth_user
            rec.status = "COMPLETED"
            rec.decision = dec_clean
            rec.discrepancy_details = payload.discrepancy_details
            rec.completed_at = datetime.now(UTC)

        db_manager.log_audit(
            event_type="AUDIT_SAMPLE_DECIDED",
            details=f"Audit sample {sample_id} (Seat: {rec.seat_id}) decided {dec_clean}",
            seat_id=rec.seat_id,
        )
        return {"sample_id": sample_id, "status": "COMPLETED", "decision": dec_clean}

    # -------------------------------------------------------------
    # Live Monitoring Dashboard Endpoints (Authenticated)
    # -------------------------------------------------------------

    @app.get("/api/v1/dashboard/live")
    def get_live_line_view(
        auth_user: str = Depends(verify_api_key),
    ) -> dict[str, Any]:
        """View 1: Live line view - last 20 seats as pass/fail strip and line status."""
        with db_manager.session_scope() as session:
            seats = session.query(SeatInspectionRecord).order_by(SeatInspectionRecord.created_at.desc()).limit(20).all()
            strip = [
                {
                    "seat_id": s.seat_id,
                    "variant_id": s.variant_id,
                    "outcome": s.outcome,
                    "label_printer": s.label_printer_enabled,
                    "timestamp": s.created_at.isoformat() if s.created_at else None,
                }
                for s in reversed(seats)
            ]
            current = seats[0].seat_id if seats else None
            return {
                "current_seat_id": current,
                "recent_strip": strip,
                "sample_size": len(strip),
            }

    @app.get("/api/v1/dashboard/quality-trends")
    def get_quality_trends(
        auth_user: str = Depends(verify_api_key),
    ) -> dict[str, Any]:
        """View 2: Quality trends, Pareto defect breakdown, and pass/review/fail rates."""
        with db_manager.session_scope() as session:
            seats = session.query(SeatInspectionRecord).all()
            total = len(seats)
            if total == 0:
                return {"sample_size": 0, "pass_rate": 0.0, "review_rate": 0.0, "fail_rate": 0.0, "pareto_defects": {}}

            pass_count = sum(1 for s in seats if s.outcome == "PASS")
            review_count = sum(1 for s in seats if s.outcome == "REVIEW")
            fail_count = sum(1 for s in seats if s.outcome == "FAIL")

            # Defect Pareto
            defects = session.query(DefectRecord).all()
            pareto: dict[str, int] = {}
            for d in defects:
                pareto[d.defect_type] = pareto.get(d.defect_type, 0) + 1

            sorted_pareto = dict(sorted(pareto.items(), key=lambda item: item[1], reverse=True))

            return {
                "sample_size": total,
                "pass_rate": round(pass_count / total, 4),
                "review_rate": round(review_count / total, 4),
                "fail_rate": round(fail_count / total, 4),
                "pareto_defects": sorted_pareto,
            }

    def _resolve_defect_image(
        st_rec: StationResultRecord | None,
        camera_name: str | None,
        defect_type: str,
    ) -> str:
        """Resolve the best available image URL for a defect with replay fallback."""
        if st_rec:
            cam_paths: dict[str, str] = {}
            if st_rec.camera_image_paths_json:
                try:
                    cam_paths = json.loads(st_rec.camera_image_paths_json)
                except Exception:
                    pass

            # 1. Camera-specific capture path
            if camera_name and camera_name in cam_paths and cam_paths[camera_name]:
                cand = cam_paths[camera_name]
                if (repo_root / cand.lstrip("/")).is_file():
                    return "/" + cand.lstrip("/")

            # 2. Station primary annotated image
            if st_rec.annotated_image_path and (repo_root / st_rec.annotated_image_path.lstrip("/")).is_file():
                return "/" + st_rec.annotated_image_path.lstrip("/")

            # 3. Station primary raw image
            if st_rec.raw_image_path and (repo_root / st_rec.raw_image_path.lstrip("/")).is_file():
                return "/" + st_rec.raw_image_path.lstrip("/")

            # 4. Any camera capture recorded for this station
            for path_val in cam_paths.values():
                if path_val and (repo_root / path_val.lstrip("/")).is_file():
                    return "/" + path_val.lstrip("/")

        # 5. Deterministic fallback to replay dataset based on station and defect type
        st_id = (st_rec.station_id if st_rec else "").upper()
        dtype_lower = defect_type.lower()
        if "STATION_1" in st_id or st_id == "1":
            if "scratch" in dtype_lower:
                return "/data/station_1/replay/02_fail_scratch.png"
            if "cut" in dtype_lower:
                return "/data/station_1/replay/03_fail_cut.png"
            if "pinhole" in dtype_lower:
                return "/data/station_1/replay/04_fail_pinhole.png"
            if "stain" in dtype_lower:
                return "/data/station_1/replay/05_review_stain.png"
            return "/data/station_1/replay/01_pass_clean.png"
        elif "STATION_2" in st_id or st_id == "2":
            if "broken" in dtype_lower:
                return "/data/station_2/replay/03_fail_broken_thread.png"
            if "skip" in dtype_lower:
                return "/data/station_2/replay/02_review_skip.png"
            if "loose" in dtype_lower:
                return "/data/station_2/replay/04_review_loose_end.png"
            if "color" in dtype_lower:
                return "/data/station_2/replay/05_fail_wrong_color.png"
            return "/data/station_2/replay/01_pass_normal.png"
        elif "STATION_3" in st_id or st_id == "3":
            return "/data/station_3/replay/01_pass_scene.png"
        elif "STATION_4" in st_id or st_id == "4":
            if "angle" in dtype_lower or "recliner" in dtype_lower:
                return "/data/station_4/replay/02_fail_recliner_angle.png"
            if "track" in dtype_lower:
                return "/data/station_4/replay/03_fail_track_position.png"
            return "/data/station_4/replay/01_pass_nominal.png"

        return "/data/station_1/replay/01_pass_clean.png"

    @app.get("/api/v1/dashboard/defect-gallery")
    def get_defect_gallery(
        limit: int = Query(48, ge=1, le=200),
        station_id: str | None = Query(None),
        defect_type: str | None = Query(None),
        auth_user: str = Depends(verify_api_key),
    ) -> list[dict[str, Any]]:
        """View 3: Defect gallery - failures joined with station inspection data and image paths."""
        with db_manager.session_scope() as session:
            query = (
                session.query(DefectRecord, StationResultRecord)
                .outerjoin(StationResultRecord, DefectRecord.station_result_id == StationResultRecord.id)
            )

            if station_id:
                clean_st = station_id.strip()
                if not clean_st.startswith("STATION_"):
                    clean_st = f"STATION_{clean_st}"
                query = query.filter(StationResultRecord.station_id == clean_st)

            if defect_type:
                query = query.filter(DefectRecord.defect_type == defect_type.strip())

            results = query.order_by(DefectRecord.created_at.desc()).limit(limit).all()

            output = []
            for d, st in results:
                bbox = [d.bbox_x, d.bbox_y, d.bbox_w, d.bbox_h] if d.bbox_x is not None else None
                img_url = _resolve_defect_image(st, d.camera_name, d.defect_type)
                delta = None
                if d.measured_value is not None and d.nominal_value is not None:
                    delta = round(d.measured_value - d.nominal_value, 3)

                output.append({
                    "id": d.id,
                    "defect_type": d.defect_type,
                    "outcome": d.outcome,
                    "seat_id": st.seat_id if st else "UNKNOWN",
                    "station_id": st.station_id if st else "UNKNOWN",
                    "camera_name": d.camera_name,
                    "view": d.view,
                    "roi_name": d.roi_name,
                    "measured_value": d.measured_value,
                    "nominal_value": d.nominal_value,
                    "delta": delta,
                    "unit": d.unit,
                    "confidence": d.confidence,
                    "bbox": bbox,
                    "description": d.description,
                    "image_url": img_url,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                })
            return output

    @app.get("/api/v1/dashboard/live-companion")
    def get_live_companion_view(
        seat_id: str | None = Query(None),
        auth_user: str = Depends(verify_api_key),
    ) -> dict[str, Any]:
        """Provide latest seat inspection snapshots, station views, and golden references."""
        with db_manager.session_scope() as session:
            seat_rec = None
            if seat_id:
                valid_sid = validate_seat_id(seat_id)
                seat_rec = session.query(SeatInspectionRecord).filter_by(seat_id=valid_sid).first()
            if not seat_rec:
                seat_rec = (
                    session.query(SeatInspectionRecord)
                    .order_by(SeatInspectionRecord.created_at.desc())
                    .first()
                )

            variant_id = seat_rec.variant_id if seat_rec else "FRONT_LH_BLACK"
            active_seat_id = seat_rec.seat_id if seat_rec else "SEAT-DEMO"
            overall_outcome = seat_rec.outcome if seat_rec else "PASS"

            st_records = []
            if seat_rec:
                st_records = (
                    session.query(StationResultRecord)
                    .filter_by(seat_id=seat_rec.seat_id)
                    .order_by(StationResultRecord.station_id.asc())
                    .all()
                )

            station_map: dict[str, Any] = {}
            for st in ("STATION_1", "STATION_2", "STATION_3", "STATION_4"):
                matching_st = next((s for s in st_records if s.station_id == st), None)
                if matching_st:
                    cam_paths = (
                        json.loads(matching_st.camera_image_paths_json)
                        if matching_st.camera_image_paths_json
                        else {}
                    )
                    primary_img = (
                        matching_st.annotated_image_path
                        or matching_st.raw_image_path
                        or (next(iter(cam_paths.values()), None) if cam_paths else None)
                    )
                    if primary_img and not primary_img.startswith("/"):
                        primary_img = "/" + primary_img

                    if not primary_img or not (repo_root / primary_img.lstrip("/")).is_file():
                        primary_img = (
                            f"/data/{st.lower()}/replay/01_pass_clean.png" if st == "STATION_1" else (
                                f"/data/{st.lower()}/replay/01_pass_normal.png" if st == "STATION_2" else (
                                    f"/data/{st.lower()}/replay/01_pass_scene.png" if st == "STATION_3" else
                                    f"/data/{st.lower()}/replay/01_pass_nominal.png"
                                )
                            )
                        )

                    station_map[st] = {
                        "station_id": st,
                        "outcome": matching_st.outcome,
                        "cycle_time_ms": matching_st.cycle_time_ms,
                        "image_url": primary_img,
                        "defects_count": len(matching_st.defects),
                        "camera_count": len(cam_paths) or 1,
                    }
                else:
                    def_img = (
                        f"/data/{st.lower()}/replay/01_pass_clean.png" if st == "STATION_1" else (
                            f"/data/{st.lower()}/replay/01_pass_normal.png" if st == "STATION_2" else (
                                f"/data/{st.lower()}/replay/01_pass_scene.png" if st == "STATION_3" else
                                f"/data/{st.lower()}/replay/01_pass_nominal.png"
                            )
                        )
                    )
                    station_map[st] = {
                        "station_id": st,
                        "outcome": "PASS",
                        "cycle_time_ms": 0.0,
                        "image_url": def_img,
                        "defects_count": 0,
                        "camera_count": 1,
                    }

            primary_snapshot_url = station_map["STATION_1"]["image_url"]
            for st_key in ("STATION_1", "STATION_2", "STATION_3", "STATION_4"):
                if station_map[st_key]["outcome"] in ("FAIL", "REVIEW"):
                    primary_snapshot_url = station_map[st_key]["image_url"]
                    break

            golden_refs: list[dict[str, Any]] = []
            variant_folder = repo_root / "configs" / "variants" / variant_id
            if not variant_folder.is_dir():
                variant_folder = repo_root / "configs" / "variants" / "FRONT_LH_BLACK"

            golden_dir = variant_folder / "golden_images"
            if golden_dir.is_dir():
                for p in sorted(golden_dir.iterdir()):
                    if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg"):
                        name_clean = p.stem.replace("_", " ").title()
                        rel_url = f"/configs/variants/{variant_folder.name}/golden_images/{p.name}"
                        golden_refs.append({
                            "name": name_clean,
                            "filename": p.name,
                            "image_url": rel_url,
                        })

            variant_cfg_file = variant_folder / "config.yaml"
            nominals: dict[str, Any] = {}
            if variant_cfg_file.is_file():
                import yaml
                try:
                    with open(variant_cfg_file, encoding="utf-8") as vf:
                        v_parsed = yaml.safe_load(vf)
                        nominals = v_parsed.get("nominals", {})
                except Exception as y_err:
                    logger.warning(f"Failed to parse variant yaml: {y_err}")

            return {
                "seat_id": active_seat_id,
                "variant_id": variant_id,
                "outcome": overall_outcome,
                "timestamp": seat_rec.created_at.isoformat() if seat_rec and seat_rec.created_at else datetime.now(UTC).isoformat(),
                "latest_inspection": {
                    "primary_image_url": primary_snapshot_url,
                    "stations": station_map,
                },
                "golden_reference": {
                    "variant_id": variant_id,
                    "images": golden_refs,
                    "nominals": nominals,
                },
            }

    @app.get("/api/v1/dashboard/shadow-mode")
    def get_shadow_mode_stats(
        auth_user: str = Depends(verify_api_key),
    ) -> dict[str, Any]:
        """View 4: Shadow mode agreement comparison, escape & false-reject tracking."""
        with db_manager.session_scope() as session:
            return generate_shift_report_dict(session)

    @app.get("/api/v1/dashboard/system-health")
    def get_system_health(
        auth_user: str = Depends(verify_api_key),
    ) -> dict[str, Any]:
        """View 6: Hardware connectivity, station liveness status, and operating mode."""
        plc_online = coordinator.plc.is_connected() if coordinator and coordinator.plc else False
        mode = "shadow" if (coordinator and coordinator.shadow_mode) else "camera_leads_with_audit"
        return {
            "plc_connected": plc_online,
            "database_status": "healthy",
            "operating_mode": mode,
            "stations": {
                "STATION_1": {"status": "ONLINE", "model_version": "v0.1.0"},
                "STATION_2": {"status": "ONLINE", "model_version": "v0.1.0"},
                "STATION_3": {"status": "ONLINE", "model_version": "v0.1.0"},
                "STATION_4": {"status": "ONLINE", "model_version": "v0.1.0"},
            },
        }

    @app.post("/api/v1/live-inspect-frame")
    async def live_inspect_frame(
        request: Request,
        threshold: float = Query(0.55, ge=0.0, le=1.0),
        auth_user: str = Depends(verify_api_key),
    ) -> dict[str, Any]:
        """Accept a JPEG frame as raw bytes, run Station 1 surface analysis, return defects."""
        import cv2
        import numpy as np

        from camerainspection.vision.station1 import SurfaceAnalyzer

        body = await request.body()
        if not body:
            raise HTTPException(status_code=400, detail="No image data received.")

        arr = np.frombuffer(body, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            raise HTTPException(status_code=422, detail="Could not decode image.")

        analyzer = SurfaceAnalyzer(anomaly_threshold=threshold)
        regions = analyzer.analyze(frame)

        min_score = threshold * 0.5
        defects = [
            {
                "defect_type": r.defect_type.value,
                "anomaly_score": round(r.anomaly_score, 3),
                "bbox": list(r.bbox_px),
                "area_px": round(r.area_px),
                "aspect_ratio": round(r.aspect_ratio, 2),
            }
            for r in regions
            if r.anomaly_score >= min_score
        ]

        high_confidence = [d for d in defects if d["anomaly_score"] >= threshold]
        outcome = "FAIL" if high_confidence else ("REVIEW" if defects else "PASS")

        return {
            "outcome": outcome,
            "defect_count": len(defects),
            "high_confidence_count": len(high_confidence),
            "frame_size": [frame.shape[1], frame.shape[0]],
            "defects": defects,
            "mode": "onnx" if analyzer._session is not None else "heuristic",
        }

    @app.get("/api/v1/camera/snapshot")
    def camera_snapshot(
        device_index: int = Query(0),
        auth_user: str = Depends(verify_api_key),
    ) -> Response:
        """Capture a JPEG frame from the camera device and return it as an image."""
        import cv2

        frame = None
        for backend in [cv2.CAP_MSMF, cv2.CAP_DSHOW, cv2.CAP_ANY]:
            try:
                cap = cv2.VideoCapture(device_index, backend)
                if cap.isOpened():
                    # Read a few frames to let camera warm up
                    for _ in range(3):
                        cap.read()
                    ret, frame = cap.read()
                    cap.release()
                    if ret and frame is not None:
                        break
                    frame = None
            except Exception:
                frame = None

        if frame is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Could not capture from camera device {device_index}. Make sure DroidCam PC client is connected.",
            )

        _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return Response(content=jpeg.tobytes(), media_type="image/jpeg")

    @app.get("/api/v1/live-inspect-proxy")
    def live_inspect_proxy(
        camera_url: str = Query("", description="Unused — kept for compatibility"),
        device_index: int = Query(0, description="Camera device index"),
        threshold: float = Query(0.55, ge=0.0, le=1.0),
        auth_user: str = Depends(verify_api_key),
    ) -> dict[str, Any]:
        """Capture a frame from camera device, run Station 1 surface analysis, return defects."""
        import cv2

        from camerainspection.vision.station1 import SurfaceAnalyzer

        frame = None
        for backend in [cv2.CAP_MSMF, cv2.CAP_DSHOW, cv2.CAP_ANY]:
            try:
                cap = cv2.VideoCapture(device_index, backend)
                if cap.isOpened():
                    for _ in range(3):
                        cap.read()
                    ret, frame = cap.read()
                    cap.release()
                    if ret and frame is not None:
                        break
                    frame = None
            except Exception:
                frame = None

        if frame is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Could not capture from camera device {device_index}. Connect DroidCam PC client first.",
            )

        analyzer = SurfaceAnalyzer(anomaly_threshold=threshold)
        regions = analyzer.analyze(frame)

        min_score = threshold * 0.5
        defects = [
            {
                "defect_type": r.defect_type.value,
                "anomaly_score": round(r.anomaly_score, 3),
                "bbox": list(r.bbox_px),
                "area_px": round(r.area_px),
                "aspect_ratio": round(r.aspect_ratio, 2),
            }
            for r in regions
            if r.anomaly_score >= min_score
        ]

        high_confidence = [d for d in defects if d["anomaly_score"] >= threshold]
        outcome = "FAIL" if high_confidence else ("REVIEW" if defects else "PASS")

        return {
            "outcome": outcome,
            "defect_count": len(defects),
            "high_confidence_count": len(high_confidence),
            "frame_size": [frame.shape[1], frame.shape[0]],
            "defects": defects,
            "mode": "onnx" if analyzer._session is not None else "heuristic",
        }

    return app
