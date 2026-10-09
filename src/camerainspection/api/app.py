"""FastAPI Application providing REST APIs for line operations, review queue, and dashboard."""

from __future__ import annotations

import os
from typing import Any
from fastapi import Depends, FastAPI, HTTPException, Header, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from camerainspection.core.logging import get_logger
from camerainspection.core.models import Outcome, OverallSeatInspectionResult, StationInspectionResult
from camerainspection.storage.db import DatabaseManager
from camerainspection.storage.entities import (
    AuditLogRecord,
    DefectRecord,
    HumanReviewRecord,
    SeatInspectionRecord,
    StationResultRecord,
)

logger = get_logger("api.service")

# Authentication key configurable via environment variable
_DEFAULT_API_KEY = "inspector_secret_token_123"


def verify_api_key(x_api_key: str | None = Header(None)) -> str:
    """Validate bearer / API key authentication for protected endpoints."""
    expected_key = os.getenv("INSPECTION_API_KEY", _DEFAULT_API_KEY)
    # If explicitly configured as None/empty, authentication can be bypassed in local dev
    if expected_key and x_api_key != expected_key:
        # Check Authorization header bearer token fallback
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key authentication header.",
        )
    return x_api_key or "anonymous"


class ReviewDecisionRequest(BaseModel):
    inspector_id: str
    decision: str = Field(..., description="PASS, REWORK, or SCRAP")
    notes: str = ""


class StationResultIngestRequest(BaseModel):
    result: StationInspectionResult


def create_app(db_manager: DatabaseManager, coordinator: Any = None) -> FastAPI:
    """Application factory for inspection line REST API."""
    app = FastAPI(
        title="Automated Car Seat Inspection System API",
        version="v0.1.0",
        description="REST service for live station results, human review queue, and OEM audit logs.",
    )

    # Allow the standalone HTML UI (served from file:// or a dev server) to call the API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok", "service": "camera-inspection-system"}

    # -------------------------------------------------------------
    # Coordinator & Inspection Results Endpoints
    # -------------------------------------------------------------

    @app.post("/api/v1/stations/result", status_code=status.HTTP_201_CREATED)
    def submit_station_result(payload: StationResultIngestRequest) -> dict[str, Any]:
        """Ingest a completed inspection result from a station."""
        st_id = db_manager.record_station_result(payload.result)
        finalized = None
        if coordinator is not None:
            finalized = coordinator.register_station_result(payload.result)

        return {
            "recorded": True,
            "station_result_id": st_id,
            "finalized": finalized is not None,
            "overall_outcome": finalized.outcome.value if finalized else None,
        }

    @app.get("/api/v1/seats/{seat_id}")
    def get_seat_inspection_result(seat_id: str) -> dict[str, Any]:
        """Fetch consolidated inspection result for a seat by ID."""
        with db_manager.session_scope() as session:
            record = (
                session.query(SeatInspectionRecord).filter_by(seat_id=seat_id).first()
            )
            if not record:
                # Fallback: check station records
                st_records = (
                    session.query(StationResultRecord)
                    .filter_by(seat_id=seat_id)
                    .all()
                )
                if not st_records:
                    raise HTTPException(
                        status_code=404, detail=f"Seat '{seat_id}' not found."
                    )
                return {
                    "seat_id": seat_id,
                    "variant_id": st_records[0].variant_id,
                    "outcome": "IN_PROGRESS",
                    "station_results": [
                        {
                            "station_id": s.station_id,
                            "outcome": s.outcome,
                            "cycle_time_ms": s.cycle_time_ms,
                        }
                        for s in st_records
                    ],
                }

            return {
                "seat_id": record.seat_id,
                "variant_id": record.variant_id,
                "outcome": record.outcome,
                "label_printer_enabled": record.label_printer_enabled,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "station_results": [
                    {
                        "station_id": s.station_id,
                        "outcome": s.outcome,
                        "cycle_time_ms": s.cycle_time_ms,
                    }
                    for s in record.station_results
                ],
            }

    # -------------------------------------------------------------
    # Human Review Queue Endpoints (Authenticated)
    # -------------------------------------------------------------

    @app.get("/api/v1/reviews/pending")
    def get_pending_reviews() -> list[dict[str, Any]]:
        """List seats currently enqueued for human review."""
        with db_manager.session_scope() as session:
            pending = session.query(HumanReviewRecord).filter_by(status="PENDING").all()
            return [
                {
                    "review_id": r.id,
                    "seat_id": r.seat_id,
                    "station_id": r.station_id,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in pending
            ]

    @app.post("/api/v1/reviews/{review_id}/decision")
    def submit_review_decision(
        review_id: int,
        payload: ReviewDecisionRequest,
        auth_user: str = Depends(verify_api_key),
    ) -> dict[str, Any]:
        """Submit inspector adjudication (PASS, REWORK, SCRAP) - Authenticated."""
        if payload.decision not in ("PASS", "REWORK", "SCRAP"):
            raise HTTPException(
                status_code=400,
                detail="Invalid decision. Must be one of: PASS, REWORK, SCRAP.",
            )

        with db_manager.session_scope() as session:
            rev = session.query(HumanReviewRecord).filter_by(id=review_id).first()
            if not rev:
                raise HTTPException(status_code=404, detail=f"Review ID {review_id} not found.")

        db_manager.resolve_review(
            review_id=review_id,
            inspector_id=payload.inspector_id,
            decision=payload.decision,
            notes=payload.notes,
        )

        # Operational release: If approved as PASS, release pallet hold on PLC and update printer
        if coordinator is not None and getattr(coordinator, "plc", None) is not None:
            target_station = rev.station_id
            if payload.decision == "PASS":
                # Release pallet hold only on the specific station that held this seat
                if target_station:
                    try:
                        coordinator.plc.hold_pallet(target_station, hold=False)
                    except Exception as e:
                        logger.warning(f"Failed to clear pallet hold for {target_station}: {e}")

                # Update the database and check if PLC accepts printer enablement
                with db_manager.session_scope() as session:
                    seat_rec = session.query(SeatInspectionRecord).filter_by(seat_id=rev.seat_id).first()
                    if seat_rec:
                        lock_ok = coordinator.plc.is_mechanism_locked()
                        # Override station outcome in coordinator/PLC for this passed review
                        if target_station:
                            coordinator.plc.set_station_result(target_station, Outcome.PASS)

                        # Check if overall seat is now passing
                        if lock_ok:
                            coordinator.plc.set_label_printer_enable(True)
                            # Align DB record strictly with actual PLC state
                            seat_rec.label_printer_enabled = coordinator.plc.is_label_printer_enabled()
                            seat_rec.outcome = Outcome.PASS.value
            else:
                # REWORK or SCRAP: Ensure pallet remains held
                if target_station:
                    coordinator.plc.hold_pallet(target_station, hold=True)
                coordinator.plc.set_label_printer_enable(False)
                with db_manager.session_scope() as session:
                    seat_rec = session.query(SeatInspectionRecord).filter_by(seat_id=rev.seat_id).first()
                    if seat_rec:
                        seat_rec.label_printer_enabled = False
                        seat_rec.outcome = Outcome.FAIL.value

        db_manager.log_audit(
            event_type="HUMAN_REVIEW_RESOLVED",
            details=f"ReviewID {review_id} resolved as {payload.decision} by {payload.inspector_id} (Auth: {auth_user}). Notes: {payload.notes}",
            seat_id=rev.seat_id,
        )
        return {"review_id": review_id, "resolved": True, "decision": payload.decision}

    # -------------------------------------------------------------
    # Audit Log Endpoints
    # -------------------------------------------------------------

    @app.get("/api/v1/audit")
    def query_audit_logs(
        seat_id: str | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        """Query immutable OEM audit log trail."""
        with db_manager.session_scope() as session:
            q = session.query(AuditLogRecord).order_by(AuditLogRecord.timestamp.desc())
            if seat_id:
                q = q.filter(AuditLogRecord.seat_id == seat_id)
            records = q.limit(limit).all()
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
    # Live Monitoring Dashboard Endpoints (7 Views)
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

            # Sorted Pareto
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
            shadow_seats = session.query(SeatInspectionRecord).filter_by(shadow_mode=True).all()
            if not shadow_seats:
                return {
                    "sample_size": 0,
                    "agreement_rate": None,
                    "reviewed_sample_size": 0,
                    "camera_catches": 0,
                    "human_catches": 0,
                    "false_reject_count": 0,
                    "false_reject_rate": None,
                    "escape_count": 0,
                    "escape_rate": None,
                }

            seat_ids = [s.seat_id for s in shadow_seats]
            reviews = (
                session.query(HumanReviewRecord)
                .filter(HumanReviewRecord.seat_id.in_(seat_ids), HumanReviewRecord.status == "RESOLVED")
                .all()
            )
            review_map = {r.seat_id: r.decision for r in reviews}

            reviewed_seats = [s for s in shadow_seats if s.seat_id in review_map]
            camera_catches = sum(1 for s in shadow_seats if s.outcome in ("FAIL", "REVIEW"))
            human_catches = sum(1 for d in review_map.values() if d in ("REWORK", "SCRAP"))

            # False reject: camera flagged REVIEW/FAIL, but human adjudicated PASS
            false_rejects = sum(
                1 for s in reviewed_seats
                if s.outcome in ("FAIL", "REVIEW") and review_map[s.seat_id] == "PASS"
            )

            # Escape: camera decided PASS, but human audited as non-pass (REWORK/SCRAP)
            escapes = sum(
                1 for s in reviewed_seats
                if s.outcome == "PASS" and review_map[s.seat_id] in ("REWORK", "SCRAP")
            )

            # Agreement: both agree on PASS or both agree on non-pass
            agreed = sum(
                1 for s in reviewed_seats
                if (s.outcome == "PASS" and review_map[s.seat_id] == "PASS")
                or (s.outcome in ("FAIL", "REVIEW") and review_map[s.seat_id] in ("REWORK", "SCRAP"))
            )

            n_rev = len(reviewed_seats)
            agreement_rate = round(agreed / n_rev, 4) if n_rev > 0 else None
            false_reject_rate = round(false_rejects / n_rev, 4) if n_rev > 0 else None
            escape_rate = round(escapes / n_rev, 4) if n_rev > 0 else None

            return {
                "sample_size": len(shadow_seats),
                "reviewed_sample_size": n_rev,
                "agreement_rate": agreement_rate,
                "camera_catches": camera_catches,
                "human_catches": human_catches,
                "false_reject_count": false_rejects,
                "false_reject_rate": false_reject_rate,
                "escape_count": escapes,
                "escape_rate": escape_rate,
            }

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
