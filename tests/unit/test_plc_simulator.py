"""Unit tests for PLCSimulator and safety interlocks."""

import pytest

from camerainspection.core.exceptions import PLCCommunicationError
from camerainspection.core.models import Outcome
from camerainspection.hardware.plc.simulator import PLCSimulator


def test_plc_connection_guard() -> None:
    plc = PLCSimulator()
    assert plc.is_connected() is False
    with pytest.raises(PLCCommunicationError):
        plc.wait_for_trigger("STATION_1")


def test_trigger_and_barcode_flow(plc_sim: PLCSimulator) -> None:
    # Timed out when no pallet arrives
    assert plc_sim.wait_for_trigger("STATION_1", timeout_s=0.1) is False

    # Simulate arrival
    plc_sim.simulate_arrival("STATION_1", barcode="SEAT1001_FRONT_LH_BLACK")
    assert plc_sim.wait_for_trigger("STATION_1", timeout_s=0.5) is True
    assert plc_sim.read_barcode("STATION_1") == "SEAT1001_FRONT_LH_BLACK"


def test_pallet_hold_on_fail_or_review(plc_sim: PLCSimulator) -> None:
    # PASS releases pallet
    plc_sim.set_station_result("STATION_1", Outcome.PASS)
    assert plc_sim.is_pallet_held("STATION_1") is False

    # REVIEW holds pallet
    plc_sim.set_station_result("STATION_2", Outcome.REVIEW)
    assert plc_sim.is_pallet_held("STATION_2") is True

    # FAIL holds pallet
    plc_sim.set_station_result("STATION_3", Outcome.FAIL)
    assert plc_sim.is_pallet_held("STATION_3") is True


def test_label_printer_safety_interlock(plc_sim: PLCSimulator) -> None:
    # Initially disabled
    assert plc_sim.is_label_printer_enabled() is False

    # Try enabling when stations haven't passed -> MUST stay disabled
    plc_sim.set_label_printer_enable(True)
    assert plc_sim.is_label_printer_enabled() is False

    # Set Station 1-3 PASS, but Station 4 REVIEW -> MUST stay disabled
    plc_sim.set_station_result("STATION_1", Outcome.PASS)
    plc_sim.set_station_result("STATION_2", Outcome.PASS)
    plc_sim.set_station_result("STATION_3", Outcome.PASS)
    plc_sim.set_station_result("STATION_4", Outcome.REVIEW)
    plc_sim.simulate_mechanism_sensor(True)

    plc_sim.set_label_printer_enable(True)
    assert plc_sim.is_label_printer_enabled() is False

    # Set Station 4 PASS, but mechanism sensor NOT confirmed -> MUST stay disabled
    plc_sim.set_station_result("STATION_4", Outcome.PASS)
    plc_sim.simulate_mechanism_sensor(False)

    plc_sim.set_label_printer_enable(True)
    assert plc_sim.is_label_printer_enabled() is False

    # All 4 stations PASS AND mechanism lock confirmed -> ALLOWED
    plc_sim.simulate_mechanism_sensor(True)
    plc_sim.set_label_printer_enable(True)
    assert plc_sim.is_label_printer_enabled() is True
