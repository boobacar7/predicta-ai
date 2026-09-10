"""PREDICTA football 1X2 ML worker.

Consumes the frozen dataset `football-1x2-history-0.3`. It does not ingest
provider data, recompute Data-layer features, call the backend, or compute value.
"""

from predicta_ml.constants import DATASET_VERSION, FEATURE_SCHEMA_VERSION, MODEL_VERSION, RANDOM_SEED

__all__ = [
    "DATASET_VERSION",
    "FEATURE_SCHEMA_VERSION",
    "MODEL_VERSION",
    "RANDOM_SEED",
]
