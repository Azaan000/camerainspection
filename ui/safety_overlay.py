"""Real-time inspection status widget for production monitoring.

Displays live inspection feed with safety check status overlays.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np


class SafetyOverlay:
    """Overlay safety check results on inspection images."""

    # Color codes (BGR format for OpenCV)
    COLOR_PASS = (0, 255, 0)  # Green
    COLOR_FAIL = (0, 0, 255)  # Red
    COLOR_REVIEW = (0, 165, 255)  # Orange
    COLOR_DISABLED = (128, 128, 128)  # Gray
    COLOR_INFO = (255, 255, 255)  # White

    @staticmethod
    def draw_status_banner(
        image: np.ndarray,
        station_id: str,
        overall_status: str,
        timestamp: datetime,
    ) -> np.ndarray:
        """Draw top banner with overall status."""
        img_with_banner = image.copy()
        h, w = img_with_banner.shape[:2]

        # Status color
        status_colors = {
            "PASS": SafetyOverlay.COLOR_PASS,
            "FAIL": SafetyOverlay.COLOR_FAIL,
            "REVIEW": SafetyOverlay.COLOR_REVIEW,
        }
        banner_color = status_colors.get(overall_status, SafetyOverlay.COLOR_DISABLED)

        # Draw banner background
        cv2.rectangle(img_with_banner, (0, 0), (w, 80), banner_color, -1)

        # Station ID
        cv2.putText(
            img_with_banner,
            station_id,
            (10, 35),
            cv2.FONT_HERSHEY_BOLD,
            1.2,
            (255, 255, 255),
            2,
        )

        # Status text
        cv2.putText(
            img_with_banner,
            f"Status: {overall_status}",
            (10, 65),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
        )

        # Timestamp
        time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            img_with_banner,
            time_str,
            (w - 300, 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        return img_with_banner

    @staticmethod
    def draw_safety_checks(
        image: np.ndarray,
        checks: list[dict[str, Any]],
    ) -> np.ndarray:
        """Draw safety check status indicators on image."""
        img_with_checks = image.copy()
        h, w = img_with_checks.shape[:2]

        # Draw checks panel on right side
        panel_width = 400
        panel_x = w - panel_width - 10
        panel_y = 100

        # Semi-transparent background
        overlay = img_with_checks.copy()
        cv2.rectangle(
            overlay,
            (panel_x, panel_y),
            (w - 10, panel_y + len(checks) * 60 + 40),
            (0, 0, 0),
            -1,
        )
        cv2.addWeighted(overlay, 0.7, img_with_checks, 0.3, 0, img_with_checks)

        # Title
        cv2.putText(
            img_with_checks,
            "Safety Checks:",
            (panel_x + 10, panel_y + 25),
            cv2.FONT_HERSHEY_BOLD,
            0.7,
            SafetyOverlay.COLOR_INFO,
            2,
        )

        # Draw each check
        y_offset = panel_y + 50
        for check in checks:
            name = check.get("name", "Unknown")
            status = check.get("status", "UNKNOWN")
            description = check.get("description", "")

            # Status indicator
            status_colors = {
                "PASS": SafetyOverlay.COLOR_PASS,
                "FAIL": SafetyOverlay.COLOR_FAIL,
                "REVIEW": SafetyOverlay.COLOR_REVIEW,
                "DISABLED": SafetyOverlay.COLOR_DISABLED,
            }
            status_color = status_colors.get(status, SafetyOverlay.COLOR_DISABLED)

            # Status circle
            cv2.circle(img_with_checks, (panel_x + 20, y_offset), 8, status_color, -1)

            # Check name
            cv2.putText(
                img_with_checks,
                name[:35],  # Truncate if too long
                (panel_x + 35, y_offset + 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                SafetyOverlay.COLOR_INFO,
                1,
            )

            # Description (smaller)
            if description:
                cv2.putText(
                    img_with_checks,
                    description[:40],
                    (panel_x + 35, y_offset + 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (200, 200, 200),
                    1,
                )

            y_offset += 60

        return img_with_checks

    @staticmethod
    def draw_defects(
        image: np.ndarray,
        defects: list[dict[str, Any]],
    ) -> np.ndarray:
        """Draw defect bounding boxes and labels."""
        img_with_defects = image.copy()

        for defect in defects:
            bbox = defect.get("bounding_box")
            if not bbox:
                continue

            x, y, w_box, h_box = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
            defect_type = defect.get("defect_type", "unknown")
            outcome = defect.get("outcome", "UNKNOWN")

            # Color by outcome
            color_map = {
                "FAIL": SafetyOverlay.COLOR_FAIL,
                "REVIEW": SafetyOverlay.COLOR_REVIEW,
                "PASS": SafetyOverlay.COLOR_PASS,
            }
            box_color = color_map.get(outcome, SafetyOverlay.COLOR_DISABLED)

            # Draw bounding box
            cv2.rectangle(img_with_defects, (x, y), (x + w_box, y + h_box), box_color, 3)

            # Draw label background
            label = f"{defect_type} ({outcome})"
            (label_w, label_h), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
            )
            cv2.rectangle(
                img_with_defects,
                (x, y - label_h - 10),
                (x + label_w + 10, y),
                box_color,
                -1,
            )

            # Draw label text
            cv2.putText(
                img_with_defects,
                label,
                (x + 5, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

        return img_with_defects

    @staticmethod
    def create_annotated_image(
        image: np.ndarray,
        station_id: str,
        overall_status: str,
        safety_checks: list[dict[str, Any]],
        defects: list[dict[str, Any]] | None = None,
        timestamp: datetime | None = None,
    ) -> np.ndarray:
        """Create fully annotated inspection image with safety overlays."""
        if timestamp is None:
            timestamp = datetime.now()

        # Add status banner
        annotated = SafetyOverlay.draw_status_banner(
            image, station_id, overall_status, timestamp
        )

        # Add safety checks panel
        annotated = SafetyOverlay.draw_safety_checks(annotated, safety_checks)

        # Add defect annotations if present
        if defects:
            annotated = SafetyOverlay.draw_defects(annotated, defects)

        return annotated


def generate_safety_report(
    station_id: str,
    inspection_result: dict[str, Any],
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Generate structured safety report from inspection results.

    Args:
        station_id: Station identifier
        inspection_result: Raw inspection results with defects and measurements
        output_path: Optional path to save JSON report

    Returns:
        Structured safety report dictionary
    """
    defects = inspection_result.get("defects", [])
    measurements = inspection_result.get("measurements", {})

    # Categorize defects by type
    safety_defects = []
    quality_defects = []
    calibration_issues = []

    for defect in defects:
        defect_type = defect.get("defect_type", "")
        if defect_type.startswith("hardware.") or defect_type.startswith("station."):
            safety_defects.append(defect)
        elif defect_type.startswith("camera."):
            calibration_issues.append(defect)
        else:
            quality_defects.append(defect)

    # Overall status
    has_fails = any(d.get("outcome") == "FAIL" for d in defects)
    has_reviews = any(d.get("outcome") == "REVIEW" for d in defects)

    if has_fails:
        overall_status = "FAIL"
    elif has_reviews:
        overall_status = "REVIEW"
    else:
        overall_status = "PASS"

    report = {
        "station_id": station_id,
        "timestamp": datetime.now().isoformat(),
        "overall_status": overall_status,
        "summary": {
            "total_defects": len(defects),
            "safety_defects": len(safety_defects),
            "quality_defects": len(quality_defects),
            "calibration_issues": len(calibration_issues),
        },
        "safety_checks": {
            "hardware_available": not any(
                d.get("defect_type") == "hardware.plc_unavailable" for d in defects
            ),
            "calibrated": len(calibration_issues) == 0,
            "golden_templates_loaded": not any(
                d.get("defect_type") == "station.missing_golden_template" for d in defects
            ),
            "measurements_valid": not any(
                d.get("defect_type") == "station.measurement_invalid" for d in defects
            ),
        },
        "measurements": measurements,
        "defects": {
            "safety": safety_defects,
            "quality": quality_defects,
            "calibration": calibration_issues,
        },
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

    return report


if __name__ == "__main__":
    # Example usage
    print("Safety overlay module loaded successfully.")
    print("Use SafetyOverlay.create_annotated_image() to add safety overlays to inspection images.")
