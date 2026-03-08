"""
Application lifecycle management module.

This module provides:
- Graceful shutdown handling
- State persistence and recovery
- Health probes (readiness, liveness)
- Data retention and cleanup
"""

from .shutdown import ShutdownManager, register_shutdown_handler
from .state_manager import StateManager, get_state_manager
from .probes import ReadinessProbe, LivenessProbe, get_readiness_probe, get_liveness_probe
from .cleanup import CleanupJob, RetentionPolicy, CleanupResult

__all__ = [
    "ShutdownManager",
    "register_shutdown_handler",
    "StateManager",
    "get_state_manager",
    "ReadinessProbe",
    "LivenessProbe",
    "get_readiness_probe",
    "get_liveness_probe",
    "CleanupJob",
    "RetentionPolicy",
    "CleanupResult",
]
