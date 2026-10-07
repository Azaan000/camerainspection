"""Template matching and hand (LH/RH) presence verification for automotive trim parts."""

from __future__ import annotations

import cv2
import numpy as np
from pydantic import BaseModel

from camerainspection.core.models import BoundingBox


class PresenceResult(BaseModel):
    component_name: str
    detected: bool
    expected_hand: str | None = None
    detected_hand: str | None = None
    is_correct_hand: bool = True
    match_score: float = 0.0
    bounding_box: BoundingBox | None = None
    message: str = ""


class GoldenTemplateMatcher:
    """Performs normalized cross-correlation template matching with hand verification."""

    @classmethod
    def match_component(
        cls,
        search_roi: np.ndarray,
        component_name: str,
        golden_template: np.ndarray,
        expected_hand: str | None = None,
        opposite_hand_template: np.ndarray | None = None,
        threshold: float = 0.80,
    ) -> PresenceResult:
        """Match component template inside search ROI with hand discrimination.

        Poka-yoke nest assumption: rotation is fixed by physical nest pins.
        """
        if search_roi.size == 0 or golden_template.size == 0:
            return PresenceResult(
                component_name=component_name,
                detected=False,
                expected_hand=expected_hand,
                is_correct_hand=False,
                match_score=0.0,
                message="Empty ROI or golden template provided.",
            )

        # Match primary golden template
        t_h, t_w = golden_template.shape[:2]
        if search_roi.shape[0] < t_h or search_roi.shape[1] < t_w:
            # ROI is smaller than template
            return PresenceResult(
                component_name=component_name,
                detected=False,
                expected_hand=expected_hand,
                is_correct_hand=False,
                match_score=0.0,
                message=f"Search ROI ({search_roi.shape[:2]}) is smaller than golden template ({t_h}, {t_w})",
            )

        res = cv2.matchTemplate(search_roi, golden_template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        primary_score = float(max_val)

        bbox = BoundingBox(x=max_loc[0], y=max_loc[1], w=t_w, h=t_h)

        # Check against opposite hand if provided and hand-sensitive
        opp_score = 0.0
        if opposite_hand_template is not None and expected_hand is not None:
            o_h, o_w = opposite_hand_template.shape[:2]
            if search_roi.shape[0] >= o_h and search_roi.shape[1] >= o_w:
                res_opp = cv2.matchTemplate(search_roi, opposite_hand_template, cv2.TM_CCOEFF_NORMED)
                _, max_val_opp, _, _ = cv2.minMaxLoc(res_opp)
                opp_score = float(max_val_opp)

        # Wrong hand detection logic
        if expected_hand and opposite_hand_template is not None:
            opp_hand = "RH" if expected_hand == "LH" else "LH"
            # If opposite hand matches significantly better than expected hand
            if opp_score >= threshold and opp_score > (primary_score + 0.05):
                return PresenceResult(
                    component_name=component_name,
                    detected=True,
                    expected_hand=expected_hand,
                    detected_hand=opp_hand,
                    is_correct_hand=False,
                    match_score=opp_score,
                    bounding_box=bbox,
                    message=f"WRONG HAND ASSEMBLED! Expected {expected_hand}, matched {opp_hand} (score={opp_score:.2f} vs {primary_score:.2f})",
                )

        if primary_score < threshold:
            # Component is missing or unrecognizable
            return PresenceResult(
                component_name=component_name,
                detected=False,
                expected_hand=expected_hand,
                detected_hand=None,
                is_correct_hand=False,
                match_score=primary_score,
                bounding_box=bbox,
                message=f"MISSING COMPONENT: {component_name} score {primary_score:.2f} below threshold {threshold:.2f}",
            )

        # Successfully matched correct component
        return PresenceResult(
            component_name=component_name,
            detected=True,
            expected_hand=expected_hand,
            detected_hand=expected_hand,
            is_correct_hand=True,
            match_score=primary_score,
            bounding_box=bbox,
            message=f"{component_name} present and verified {expected_hand or 'N/A'} (score={primary_score:.2f})",
        )
