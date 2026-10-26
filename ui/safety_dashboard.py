"""Safety Dashboard UI for Camera Inspection System.

Displays real-time status of critical safety checks across all stations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import streamlit as st


@dataclass
class SafetyCheck:
    """Individual safety check status."""

    name: str
    status: str  # "PASS", "FAIL", "REVIEW", "DISABLED"
    description: str
    last_updated: datetime
    details: dict[str, Any] | None = None


@dataclass
class StationStatus:
    """Station-level safety status."""

    station_id: str
    station_name: str
    enabled: bool
    safety_checks: list[SafetyCheck]
    last_inspection: datetime | None = None
    total_inspections: int = 0
    escape_rate: float = 0.0


def render_safety_badge(status: str) -> str:
    """Render colored badge for safety status."""
    colors = {
        "PASS": "🟢",
        "FAIL": "🔴",
        "REVIEW": "🟡",
        "DISABLED": "⚫",
        "UNKNOWN": "⚪",
    }
    return colors.get(status, "⚪")


def render_station_card(station: StationStatus) -> None:
    """Render a station safety status card."""
    with st.container():
        col1, col2, col3 = st.columns([3, 1, 1])

        with col1:
            st.subheader(f"{station.station_id}: {station.station_name}")

        with col2:
            if station.enabled:
                st.success("ENABLED")
            else:
                st.warning("DISABLED")

        with col3:
            if station.escape_rate > 0.005:  # Above target
                st.error(f"Escape: {station.escape_rate:.3%}")
            else:
                st.metric("Escape Rate", f"{station.escape_rate:.3%}")

        # Safety checks table
        if station.safety_checks:
            st.markdown("#### Critical Safety Checks")
            for check in station.safety_checks:
                with st.expander(
                    f"{render_safety_badge(check.status)} {check.name}", expanded=False
                ):
                    st.write(f"**Status:** {check.status}")
                    st.write(f"**Description:** {check.description}")
                    st.write(f"**Last Updated:** {check.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
                    if check.details:
                        st.json(check.details)

        # Inspection stats
        if station.last_inspection:
            st.caption(
                f"Last Inspection: {station.last_inspection.strftime('%Y-%m-%d %H:%M:%S')} "
                f"| Total: {station.total_inspections:,}"
            )

        st.divider()


def create_safety_dashboard(stations: list[StationStatus]) -> None:
    """Create main safety dashboard UI."""
    st.set_page_config(
        page_title="Camera Inspection Safety Dashboard",
        page_icon="🔒",
        layout="wide",
    )

    st.title("🔒 Camera Inspection System - Safety Dashboard")
    st.caption(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Overall system status
    total_enabled = sum(1 for s in stations if s.enabled)
    total_checks = sum(len(s.safety_checks) for s in stations)
    failing_checks = sum(
        1 for s in stations for c in s.safety_checks if c.status == "FAIL"
    )
    review_checks = sum(
        1 for s in stations for c in s.safety_checks if c.status == "REVIEW"
    )

    # KPI metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Active Stations", f"{total_enabled}/{len(stations)}")
    with col2:
        if failing_checks > 0:
            st.metric("Failing Checks", failing_checks, delta=f"-{failing_checks}", delta_color="inverse")
        else:
            st.metric("Failing Checks", "0", delta="✓ All Pass")
    with col3:
        st.metric("Review Needed", review_checks)
    with col4:
        avg_escape = sum(s.escape_rate for s in stations) / len(stations) if stations else 0
        if avg_escape > 0.005:
            st.metric("Avg Escape Rate", f"{avg_escape:.3%}", delta="⚠️ Above Target")
        else:
            st.metric("Avg Escape Rate", f"{avg_escape:.3%}", delta="✓ On Target")

    st.divider()

    # Station cards
    st.markdown("## Station Details")
    for station in stations:
        render_station_card(station)


def get_mock_data() -> list[StationStatus]:
    """Get mock data for testing (replace with real data connector)."""
    now = datetime.now()

    return [
        StationStatus(
            station_id="STATION_1",
            station_name="Leather Inspection",
            enabled=True,
            safety_checks=[
                SafetyCheck(
                    name="ONNX Engine Validation",
                    status="PASS",
                    description="AI model returns valid predictions (not engine errors)",
                    last_updated=now,
                    details={"engine": "onnxruntime", "model_version": "v2.1.0"},
                ),
                SafetyCheck(
                    name="ROI Boundary Validation",
                    status="PASS",
                    description="All ROIs within image bounds",
                    last_updated=now,
                ),
            ],
            last_inspection=now,
            total_inspections=1247,
            escape_rate=0.0018,
        ),
        StationStatus(
            station_id="STATION_2",
            station_name="Stitch Inspection",
            enabled=True,
            safety_checks=[
                SafetyCheck(
                    name="Measurement Range Validation",
                    status="PASS",
                    description="SPI in range 1-20, stitch count ≥ 3",
                    last_updated=now,
                    details={"spi_range": [1, 20], "min_stitches": 3},
                ),
                SafetyCheck(
                    name="Broken Thread Detector",
                    status="PASS",
                    description="Heuristic gap detection (>3x pitch, >5mm)",
                    last_updated=now,
                    details={"method": "heuristic", "min_gap_mm": 5.0},
                ),
            ],
            last_inspection=now,
            total_inspections=983,
            escape_rate=0.0042,
        ),
        StationStatus(
            station_id="STATION_3",
            station_name="Plastic Parts Inspection",
            enabled=True,
            safety_checks=[
                SafetyCheck(
                    name="Golden Template Requirement",
                    status="PASS",
                    description="Template present for all variant/component pairs",
                    last_updated=now,
                    details={"templates_loaded": 12, "missing": 0},
                ),
                SafetyCheck(
                    name="Image Sanity Check",
                    status="PASS",
                    description="Detects unrelated images (edge density, color family)",
                    last_updated=now,
                ),
                SafetyCheck(
                    name="Camera Calibration Check",
                    status="REVIEW",
                    description="Camera uncalibrated - reporting pixels instead of mm",
                    last_updated=now,
                    details={"pixel_size_mm": 0.18, "is_default": True},
                ),
            ],
            last_inspection=now,
            total_inspections=756,
            escape_rate=0.0031,
        ),
        StationStatus(
            station_id="STATION_4",
            station_name="Complete Seat & Mechanism",
            enabled=True,
            safety_checks=[
                SafetyCheck(
                    name="PLC Availability Check",
                    status="PASS",
                    description="PLC hardware available for mechanism verification",
                    last_updated=now,
                    details={"plc_connected": True, "plc_type": "Siemens S7-1200"},
                ),
                SafetyCheck(
                    name="Lock Sensor Confirmation",
                    status="PASS",
                    description="Mechanism lock sensor confirmed (required=1.0)",
                    last_updated=now,
                    details={"lock_confirmed": 1.0, "required": 1.0},
                ),
                SafetyCheck(
                    name="Camera Calibration Check",
                    status="PASS",
                    description="Camera calibrated for track position measurement",
                    last_updated=now,
                    details={"pixel_size_mm": 0.15, "is_calibrated": True},
                ),
            ],
            last_inspection=now,
            total_inspections=542,
            escape_rate=0.0009,
        ),
    ]


def main():
    """Main entry point for safety dashboard."""
    stations = get_mock_data()
    create_safety_dashboard(stations)


if __name__ == "__main__":
    main()
