"""Station 3 Plastic Parts Inspection Vision Modules."""

from camerainspection.vision.station3.color import ColorMatchEngine
from camerainspection.vision.station3.dimensions import PlasticDimensionEngine
from camerainspection.vision.station3.presence import GoldenTemplateMatcher, PresenceResult

__all__ = [
    "ColorMatchEngine",
    "PlasticDimensionEngine",
    "GoldenTemplateMatcher",
    "PresenceResult",
]
