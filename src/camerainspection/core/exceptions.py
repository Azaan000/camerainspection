"""Domain-specific exceptions for camera inspection system."""


class InspectionSystemError(Exception):
    """Base exception for all camera inspection system errors."""


class HardwareError(InspectionSystemError):
    """Base exception for hardware communication and acquisition issues."""


class CameraError(HardwareError):
    """Base camera error."""


class CameraOfflineError(CameraError):
    """Camera disconnected or unavailable."""


class CameraTimeoutError(CameraError):
    """Camera acquisition timed out."""


class CorruptImageError(CameraError):
    """Captured image is empty, malformed, or corrupt."""


class PLCError(HardwareError):
    """Base PLC error."""


class PLCCommunicationError(PLCError):
    """Lost connection or failed register read/write on PLC."""


class PLCTriggerTimeoutError(PLCError):
    """Timed out waiting for station trigger signal."""


class ConfigurationError(InspectionSystemError):
    """Configuration parsing or schema error."""


class UnknownVariantError(ConfigurationError):
    """Barcode resolved to an unrecognized or missing variant configuration."""


class InvalidBarcodeError(InspectionSystemError):
    """Barcode is blank, unreadable, or checksum-invalid."""


class InferenceEngineError(InspectionSystemError):
    """Model inference failure or uncalibrated confidence score."""
