"""FastAPI Application providing REST APIs for line operations, review queue, and dashboard."""

from __future__ import annotations

from typing import Any
from fastapi import FastAPI, HTTPException, Query, status
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
    def get_seat_record(seat_id: str) -> dict[str, Any]:
        """Fetch full inspection status, defects, and station history for a seat."""
        with db_manager.session_scope() as session:
            seat = session.query(SeatInspectionRecord).filter_by(seat_id=seat_id).first()
            if not seat:
                raise HTTPException(status_code=404, detail=f"Seat ID {seat_id} not found.")

            results_data = []
            for sr in seat.station_results:
                defects_data = [
                    {
                        "defect_type": d.defect_type,
                        "outcome": d.outcome,
                        "measured_value": d.measured_value,
                        "nominal_value": d.nominal_value,
                        "unit": d.unit,
                        "confidence": d.confidence,
                        "description": d.description,
                        "bbox": [d.bbox_x, d.bbox_y, d.bbox_w, d.bbox_h],
                    }
                    for d in sr.defects
                ]
                results_data.append({
                    "station_id": sr.station_id,
                    "outcome": sr.outcome,
                    "cycle_time_ms": sr.cycle_time_ms,
                    "model_version": sr.model_version,
                    "defects": defects_data,
                })

            return {
                "seat_id": seat.seat_id,
                "variant_id": seat.variant_id,
                "outcome": seat.outcome,
                "label_printer_enabled": seat.label_printer_enabled,
                "mechanism_cycle_passed": seat.mechanism_cycle_passed,
                "lock_sensor_confirmed": seat.lock_sensor_confirmed,
                "shadow_mode": seat.shadow_mode,
                "created_at": seat.created_at.isoformat() if seat.created_at else None,
                "completed_at": seat.completed_at.isoformat() if seat.completed_at else None,
                "station_results": results_data,
            }

    # -------------------------------------------------------------
    # Human Review Queue Endpoints
    # -------------------------------------------------------------

    @app.get("/api/v1/reviews/pending")
    def list_pending_reviews() -> list[dict[str, Any]]:
        """List seats currently waiting in the human review queue."""
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
    def submit_review_decision(review_id: int, payload: ReviewDecisionRequest) -> dict[str, Any]:
        """Submit inspector adjudication (PASS, REWORK, SCRAP)."""
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
        db_manager.log_audit(
            event_type="HUMAN_REVIEW_RESOLVED",
            details=f"ReviewID {review_id} resolved as {payload.decision} by {payload.inspector_id}. Notes: {payload.notes}",
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

    return app
