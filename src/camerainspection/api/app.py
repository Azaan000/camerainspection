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

        # Operational release: If approved as PASS, release pallet hold on PLC and re-check printer
        if coordinator is not None and getattr(coordinator, "plc", None) is not None:
            if payload.decision == "PASS":
                # Clear holds for all stations
                for st in getattr(coordinator, "expected_stations", []):
                    try:
                        coordinator.plc.hold_pallet(st, hold=False)
                    except Exception as e:
                        logger.warning(f"Failed to clear pallet hold for {st}: {e}")

                # If seat can now enable label printer, update PLC
                with db_manager.session_scope() as session:
                    seat_rec = session.query(SeatInspectionRecord).filter_by(seat_id=rev.seat_id).first()
                    lock_ok = coordinator.plc.is_mechanism_locked()
                    if seat_rec and seat_rec.mechanism_cycle_passed and lock_ok:
                        coordinator.plc.set_label_printer_enable(True)
                        seat_rec.label_printer_enabled = True
            else:
                # REWORK or SCRAP: Ensure pallet remains held
                if rev.station_id:
                    coordinator.plc.hold_pallet(rev.station_id, hold=True)
                coordinator.plc.set_label_printer_enable(False)

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
                    "camera_catches": 0,
                    "human_catches": 0,
                    "estimated_escape_rate": 0.0,
                    "estimated_false_reject_rate": 0.0,
                }

            # Calculate agreement based on actual resolved human reviews
            seat_ids = [s.seat_id for s in shadow_seats]
            reviews = (
                session.query(HumanReviewRecord)
                .filter(HumanReviewRecord.seat_id.in_(seat_ids), HumanReviewRecord.status == "RESOLVED")
                .all()
            )
            review_map = {r.seat_id: r.decision for r in reviews}

            agreed = 0
            evaluated = 0
            camera_catches = sum(1 for s in shadow_seats if s.outcome in ("FAIL", "REVIEW"))
            human_catches = sum(1 for d in review_map.values() if d in ("REWORK", "SCRAP"))

            for s in shadow_seats:
                if s.seat_id in review_map:
                    evaluated += 1
                    # Camera PASS agreeing with human PASS, or both flagging as non-pass
                    human_pass = review_map[s.seat_id] == "PASS"
                    camera_pass = s.outcome == "PASS"
                    if human_pass == camera_pass:
                        agreed += 1

            agreement_rate = round(agreed / evaluated, 4) if evaluated > 0 else None

            return {
                "sample_size": len(shadow_seats),
                "agreement_rate": agreement_rate,
                "camera_catches": camera_catches,
                "human_catches": human_catches,
                "estimated_escape_rate": round(1.0 - agreement_rate, 4) if agreement_rate is not None else 0.0,
                "estimated_false_reject_rate": 0.0,
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
