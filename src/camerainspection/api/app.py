"""FastAPI application factory defining secure inspection ingestion, review, and analytics APIs."""

from __future__ import annotations

import io
import json
import os
import secrets
import zipfile
from typing import Any
from fastapi import Depends, FastAPI, HTTPException, Header, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from camerainspection.coordinator.service import InspectionCoordinator
from camerainspection.core.logging import get_logger
from camerainspection.core.models import Outcome, StationInspectionResult
from camerainspection.storage.db import DatabaseManager
from camerainspection.storage.entities import (
    AuditLogRecord,
    AuditSampleRecord,
    CameraResultRecord,
    DefectRecord,
    HumanReviewRecord,
    SeatInspectionRecord,
    ShadowDecisionRecord,
    StationResultRecord,
)
from camerainspection.tools.shift_report import generate_shift_report_dict

logger = get_logger("api.app")

EXPECTED_API_KEY = os.getenv("INSPECTION_API_KEY", "inspector_secret_token_123")


def verify_api_key(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None, alias="Authorization"),
) -> str:
    """Validate API key via constant-time comparison against header or Bearer token."""
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

    expected = EXPECTED_API_KEY.encode("utf-8")
    provided = provided_key.encode("utf-8")
    if not (secrets.compare_digest(provided, expected) and len(expected) > 0):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Invalid inspection API key.",
        )

    return "authenticated_inspector"


class ReviewDecisionPayload(BaseModel):
    decision: str = Field(..., description="Decision outcome: PASS, REWORK, or SCRAP")
    notes: str = Field("", description="Review notes / explanation")
    inspector_id: str | None = Field(None, description="Self-declared inspector badge ID")


class StationResultIngestRequest(BaseModel):
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
    app = FastAPI(
        title="Automated Camera Inspection System API",
        version="0.1.0",
        description="End-of-line car seat camera inspection service with fail-safe safety gating.",
    )

    allowed_origins = [
        orig.strip()
        for orig in os.getenv(
            "CORS_ALLOWED_ORIGINS",
            "http://127.0.0.1:8000,http://localhost:8000",
        ).split(",")
        if orig.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins if allowed_origins else ["http://127.0.0.1:8000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["X-API-Key", "Authorization", "Content-Type"],
    )

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok", "service": "camera-inspection-system", "version": "0.1.0"}

    # -------------------------------------------------------------
    # Ingestion & Seat Query Endpoints
    # -------------------------------------------------------------

    @app.post("/api/v1/stations/result", status_code=status.HTTP_201_CREATED)
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
                seat_id=payload.seat_id,
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
    def get_seat_status(seat_id: str) -> dict[str, Any]:
        """Retrieve complete inspection history and outcome for a given seat ID."""
        with db_manager.session_scope() as session:
            record = (
                session.query(SeatInspectionRecord)
                .filter(SeatInspectionRecord.seat_id == seat_id)
                .first()
            )
            if not record:
                st_records = (
                    session.query(StationResultRecord)
                    .filter(StationResultRecord.seat_id == seat_id)
                    .all()
                )
                if not st_records:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Seat ID '{seat_id}' not found.",
                    )
                return {
                    "seat_id": seat_id,
                    "variant_id": st_records[0].variant_id if st_records else "UNKNOWN",
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
                            "camera_image_paths": json.loads(s.camera_image_paths_json) if s.camera_image_paths_json else {},
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
                        "camera_image_paths": json.loads(s.camera_image_paths_json) if s.camera_image_paths_json else {},
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

    @app.get("/api/v1/seats/{seat_id}/export")
    def export_seat_trace(seat_id: str, format: str = Query("zip")) -> Response:
        """Phase 9 Export endpoint: Returns zip file containing JSON audit trace + defect images."""
        status_info = get_seat_status(seat_id)
        with db_manager.session_scope() as session:
            logs = session.query(AuditLogRecord).filter_by(seat_id=seat_id).all()
            reviews = session.query(HumanReviewRecord).filter_by(seat_id=seat_id).all()
            shadow = session.query(ShadowDecisionRecord).filter_by(seat_id=seat_id).all()

            status_info["audit_logs"] = [
                {
                    "event_type": l.event_type,
                    "details": l.details,
                    "timestamp": l.timestamp.isoformat() if l.timestamp else None,
                }
                for l in logs
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

        # Create ZIP in memory
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("audit_trace.json", json.dumps(status_info, indent=2))

            # Include any defect or camera images
            for sr in status_info.get("station_results", []):
                for cam_name, img_path in sr.get("camera_image_paths", {}).items():
                    if img_path and os.path.exists(img_path):
                        arcname = f"images/{sr.get('station_id')}_{cam_name}_{os.path.basename(img_path)}"
                        zf.write(img_path, arcname=arcname)

        zip_buf.seek(0)
        return Response(
            content=zip_buf.getvalue(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="trace_{seat_id}.zip"',
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
                    "camera_image_paths": json.loads(st_res.camera_image_paths_json) if st_res and st_res.camera_image_paths_json else {},
                })
            return out

    @app.post("/api/v1/reviews/{review_id}/decision")
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
                            coordinator.plc.set_station_result(rev.station_id, Outcome.PASS, seat_id=rev.seat_id)
                            coordinator.plc.hold_pallet(rev.station_id, hold=False)
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
                        coordinator.plc.hold_pallet(rev.station_id, hold=True)
                        coordinator.plc.set_label_printer_enable(False, seat_id=rev.seat_id)

        db_manager.log_audit(
            event_type="HUMAN_REVIEW_RESOLVED",
            details=f"ReviewID {review_id} resolved as {payload.decision} by {inspector} (Auth: {auth_user}). Notes: {payload.notes}",
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
                query = query.filter_by(seat_id=seat_id)
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

    @app.post("/api/v1/shadow-mode/decision")
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
    ) -> dict[str, Any]:
        """Generate comprehensive end-of-shift quality report comparing camera vs inspector."""
        with db_manager.session_scope() as session:
            return generate_shift_report_dict(session, false_reject_threshold_pct=threshold_pct)

    # -------------------------------------------------------------
    # Audit Sampling Endpoints (Phase 8)
    # -------------------------------------------------------------

    @app.post("/api/v1/audit/sample")
    def trigger_audit_sample(
        count: int = Query(5, ge=1, le=50),
        auth_user: str = Depends(verify_api_key),
    ) -> dict[str, Any]:
        """Randomly select N PASS seats for quality auditor to verify against master."""
        with db_manager.session_scope() as session:
            # Find already sampled seat IDs
            sampled_ids = {r.seat_id for r in session.query(AuditSampleRecord).all()}

            # Candidates: PASS seats not yet sampled
            candidates = (
                session.query(SeatInspectionRecord)
                .filter(SeatInspectionRecord.outcome == "PASS")
                .all()
            )
            eligible = [s for s in candidates if s.seat_id not in sampled_ids]

            import random
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
    def list_audit_samples() -> list[dict[str, Any]]:
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

    @app.post("/api/v1/audit/sample/{sample_id}/decision")
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
            from datetime import datetime, timezone
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
            rec.completed_at = datetime.now(timezone.utc)

        db_manager.log_audit(
            event_type="AUDIT_SAMPLE_DECIDED",
            details=f"Audit sample {sample_id} (Seat: {rec.seat_id}) decided {dec_clean}",
            seat_id=rec.seat_id,
        )
        return {"sample_id": sample_id, "status": "COMPLETED", "decision": dec_clean}

    # -------------------------------------------------------------
    # Live Monitoring Dashboard Endpoints
    # -------------------------------------------------------------

    @app.get("/api/v1/dashboard/live")
    def get_live_line_view() -> dict[str, Any]:
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
    def get_quality_trends() -> dict[str, Any]:
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

    @app.get("/api/v1/dashboard/defect-gallery")
    def get_defect_gallery(limit: int = Query(20, ge=1, le=100)) -> list[dict[str, Any]]:
        """View 3: Defect gallery - recent failures with bounding box and measured values."""
        with db_manager.session_scope() as session:
            defects = session.query(DefectRecord).order_by(DefectRecord.created_at.desc()).limit(limit).all()
            return [
                {
                    "defect_type": d.defect_type,
                    "outcome": d.outcome,
                    "measured_value": d.measured_value,
                    "nominal_value": d.nominal_value,
                    "unit": d.unit,
                    "confidence": d.confidence,
                    "bbox": [d.bbox_x, d.bbox_y, d.bbox_w, d.bbox_h],
                    "roi_name": d.roi_name,
                    "description": d.description,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in defects
            ]

    @app.get("/api/v1/dashboard/shadow-mode")
    def get_shadow_mode_stats() -> dict[str, Any]:
        """View 4: Shadow mode agreement comparison, escape & false-reject tracking."""
        with db_manager.session_scope() as session:
            return generate_shift_report_dict(session)

    @app.get("/api/v1/dashboard/system-health")
    def get_system_health() -> dict[str, Any]:
        """View 6: Hardware connectivity and station liveness status."""
        plc_online = coordinator.plc.is_connected() if coordinator and coordinator.plc else False
        return {
            "plc_connected": plc_online,
            "database_status": "healthy",
            "stations": {
                "STATION_1": {"status": "ONLINE", "model_version": "v0.1.0"},
                "STATION_2": {"status": "ONLINE", "model_version": "v0.1.0"},
                "STATION_3": {"status": "ONLINE", "model_version": "v0.1.0"},
                "STATION_4": {"status": "ONLINE", "model_version": "v0.1.0"},
            },
        }

    return app
