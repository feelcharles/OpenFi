"""
Event Bus Module

Redis-based publish-subscribe event bus for inter-module communication.
"""

from .event_bus import EventBus
from .models import Event, RawDataEvent, HighValueSignalEvent, TradingSignalEvent
from .serializer import EventSerializer
from .dead_letter_queue import DeadLetterQueue, FailedEvent
from .metrics import EventMetrics

__all__ = [
    "EventBus",
    "Event",
    "RawDataEvent",
    "HighValueSignalEvent",
    "TradingSignalEvent",
    "EventSerializer",
    "DeadLetterQueue",
    "FailedEvent",
    "EventMetrics"
]
