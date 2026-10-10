"""Industrial Line Controller managing conveyor sequences, emergency stop, and reject diversion."""

from __future__ import annotations

import threading
from typing import Any

from camerainspection.core.logging import get_logger
from camerainspection.core.models import Outcome
from camerainspection.line.builder import LineRuntime

logger = get_logger("line.controller")


class LineController:
    """Controls physical material handling, safety interlocks, and pallet traversal across inspection stations."""

    def __init__(self, runtime: LineRuntime) -> None:
        self.runtime = runtime
        self._lock = threading.Lock()
        self._emergency_stopped = False
        self._running = False

    def trigger_emergency_stop(self) -> None:
        """Trigger line-wide E-Stop: stops conveyor immediately, holds pallets, and turns off printer."""
        with self._lock:
            self._emergency_stopped = True
            logger.critical("LINE EMERGENCY STOP ENGAGED!")

            # 1. Stop conveyor
            if self.runtime.conveyor:
                self.runtime.conveyor.stop()

            # 2. Hard-disable label printer
            if self.runtime.plc:
                self.runtime.plc.set_label_printer_enable(False)

            # 3. Hold pallets at all stations
            if self.runtime.plc:
                for st in self.runtime.config.coordinator.expected_stations:
                    self.runtime.plc.hold_pallet(st, hold=True)

            # 4. Sound operator alarm & update panel indicator
            if self.runtime.operator_panel:
                self.runtime.operator_panel.set_indicator("red", True)
                self.runtime.operator_panel.set_indicator("green", False)

    def reset_emergency_stop(self) -> None:
        """Clear E-Stop and return to safe standby."""
        with self._lock:
            self._emergency_stopped = False
            logger.info("Line Emergency Stop reset by operator.")
            if self.runtime.operator_panel:
                self.runtime.operator_panel.set_indicator("amber", True)
                self.runtime.operator_panel.set_indicator("red", False)

    def is_emergency_stopped(self) -> bool:
        return self._emergency_stopped

    def run_seat_cycle(self, seat_id: str, variant_id: str = "FRONT_LH_BLACK") -> dict[str, Any]:
        """Execute full seat traversal through all 4 inspection stations with conveyor and diverter logic."""
        if self._emergency_stopped:
            logger.error(f"Cannot process seat {seat_id}: Line is currently in EMERGENCY STOP.")
            return {"seat_id": seat_id, "outcome": Outcome.FAIL, "status": "ABORTED_ESTOP"}

        # Write RFID tag
        try:
            self.runtime.rfid.write_tag(seat_id)
        except Exception as e:
            logger.error(f"RFID write error for {seat_id}: {e}")

        barcode = f"{seat_id}_{variant_id}"
        overall_outcome = None
        station_results = {}

        for st_name, st_service in self.runtime.stations.items():
            if self._emergency_stopped:
                logger.warning(f"Cycle aborted mid-sequence for {seat_id} due to E-Stop at {st_name}.")
                return {"seat_id": seat_id, "outcome": Outcome.FAIL, "status": "ABORTED_ESTOP"}

            # Simulate arrival at station
            if hasattr(self.runtime.plc, "simulate_arrival"):
                self.runtime.plc.simulate_arrival(st_name, barcode)

            # Run station inspection cycle
            res = st_service.run_cycle()
            station_results[st_name] = res

            # Register with coordinator
            overall = self.runtime.coordinator.register_station_result(res)
            if overall:
                overall_outcome = overall

        # Line Material Routing (Problem 14 / C4)
        if overall_outcome and overall_outcome.outcome == Outcome.PASS and overall_outcome.label_printer_enabled:
            # Clean pass: release pallet to mainline conveyor and apply label
            self.runtime.conveyor.release_to_mainline(seat_id)
            self.runtime.coordinator.mark_seat_printed(seat_id)
            if self.runtime.operator_panel:
                self.runtime.operator_panel.set_indicator("green", True)
                self.runtime.operator_panel.set_indicator("red", False)
            logger.info(f"Seat {seat_id} PASSED and released to mainline.")
            return {
                "seat_id": seat_id,
                "outcome": Outcome.PASS,
                "label_printed": True,
                "station_results": station_results,
            }
        else:
            # Defect or Review: divert pallet to reject spur and ensure printer is unenergized
            self.runtime.conveyor.divert_to_reject(seat_id)
            if self.runtime.operator_panel:
                self.runtime.operator_panel.set_indicator("red", True)
                self.runtime.operator_panel.set_indicator("green", False)
            logger.warning(f"Seat {seat_id} FAILED/REVIEW and diverted to reject spur.")
            return {
                "seat_id": seat_id,
                "outcome": overall_outcome.outcome if overall_outcome else Outcome.FAIL,
                "label_printed": False,
                "station_results": station_results,
            }
