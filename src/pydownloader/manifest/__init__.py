"""Package for detecting, filtering and registering found sources."""

from pydownloader.manifest.detector import Candidate, classify
from pydownloader.manifest.drm import DrmVerdict, detect_drm
from pydownloader.manifest.pipeline import Outcome, process_event
from pydownloader.manifest.quality import QualityDecision, QualityFilter
from pydownloader.manifest.registry import SourceEntry, SourceRegistry

__all__ = [
    "Candidate",
    "DrmVerdict",
    "Outcome",
    "QualityDecision",
    "QualityFilter",
    "SourceEntry",
    "SourceRegistry",
    "classify",
    "detect_drm",
    "process_event",
]
