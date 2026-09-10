from __future__ import annotations


class PredictaMlError(Exception):
    """Base error for the football ML worker."""


class DatasetError(PredictaMlError):
    """The frozen dataset is missing, mismatched, or internally inconsistent."""


class TemporalLeakageError(PredictaMlError):
    """Train/validation/test rows violate chronological isolation."""


class RegistryError(PredictaMlError):
    """Model registry artefact cannot be written or reloaded."""
