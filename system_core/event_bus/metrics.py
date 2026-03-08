"""
Event Bus Metrics

Prometheus metrics tracking for Event Bus operations including message count,
queue depth, latency, and error rate.
"""

from typing import Optional
from prometheus_client import Counter, Gauge, Histogram, start_http_server, CollectorRegistry, REGISTRY
import time

class EventMetrics:
    """
    Prometheus metrics for Event Bus.
    
    Tracks:
    - Total messages published/received
    - Queue depth per topic
    - Processing latency
    - Error rate
    
    All metrics are labeled by topic and event_type for granular monitoring.
    """
    
    # Class-level registry to track if metrics are already created
    _metrics_created = False
    _shared_metrics = {}
    
    def __init__(self, port: int = 8001, registry: Optional[CollectorRegistry] = None):
        """
        Initialize Event Bus metrics.
        
        Args:
            port: Port to expose metrics endpoint (default: 8001)
            registry: Prometheus registry to use (default: REGISTRY)
        """
        self.port = port
        self._server_started = False
        self.registry = registry or REGISTRY
        
        # Use shared metrics if already created, otherwise create new ones
        if not EventMetrics._metrics_created:
            # Counter: Total messages published
            self.messages_published = Counter(
                'event_bus_messages_published_total',
                'Total number of messages published to Event Bus',
                ['topic', 'event_type'],
                registry=self.registry
            )
            
            # Counter: Total messages received
            self.messages_received = Counter(
                'event_bus_messages_received_total',
                'Total number of messages received from Event Bus',
                ['topic', 'event_type'],
                registry=self.registry
            )
            
            # Gauge: Current queue depth per topic
            self.queue_depth = Gauge(
                'event_bus_queue_depth',
                'Current queue depth for each topic',
                ['topic'],
                registry=self.registry
            )
            
            # Histogram: Message processing latency
            self.processing_latency = Histogram(
                'event_bus_processing_latency_seconds',
                'Time taken to process messages',
                ['topic', 'event_type'],
                buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
                registry=self.registry
            )
            
            # Counter: Total errors
            self.errors = Counter(
                'event_bus_errors_total',
                'Total number of errors in Event Bus operations',
                ['topic', 'event_type', 'error_type'],
                registry=self.registry
            )
            
            # Gauge: In-flight messages
            self.in_flight_messages = Gauge(
                'event_bus_in_flight_messages',
                'Number of messages currently being processed',
                registry=self.registry
            )
            
            # Store in shared metrics
            EventMetrics._shared_metrics = {
                'messages_published': self.messages_published,
                'messages_received': self.messages_received,
                'queue_depth': self.queue_depth,
                'processing_latency': self.processing_latency,
                'errors': self.errors,
                'in_flight_messages': self.in_flight_messages
            }
            EventMetrics._metrics_created = True
        else:
            # Reuse existing metrics
            self.messages_published = EventMetrics._shared_metrics['messages_published']
            self.messages_received = EventMetrics._shared_metrics['messages_received']
            self.queue_depth = EventMetrics._shared_metrics['queue_depth']
            self.processing_latency = EventMetrics._shared_metrics['processing_latency']
            self.errors = EventMetrics._shared_metrics['errors']
            self.in_flight_messages = EventMetrics._shared_metrics['in_flight_messages']
    
    def start_server(self) -> None:
        """Start Prometheus metrics HTTP server."""
        if not self._server_started:
            start_http_server(self.port, registry=self.registry)
            self._server_started = True
    
    def record_publish(self, topic: str, event_type: str) -> None:
        """
        Record a message publish event.
        
        Args:
            topic: Topic name
            event_type: Event type
        """
        self.messages_published.labels(topic=topic, event_type=event_type).inc()
    
    def record_receive(self, topic: str, event_type: str) -> None:
        """
        Record a message receive event.
        
        Args:
            topic: Topic name
            event_type: Event type
        """
        self.messages_received.labels(topic=topic, event_type=event_type).inc()
    
    def set_queue_depth(self, topic: str, depth: int) -> None:
        """
        Set current queue depth for a topic.
        
        Args:
            topic: Topic name
            depth: Current queue depth
        """
        self.queue_depth.labels(topic=topic).set(depth)
    
    def record_latency(self, topic: str, event_type: str, latency_seconds: float) -> None:
        """
        Record message processing latency.
        
        Args:
            topic: Topic name
            event_type: Event type
            latency_seconds: Processing time in seconds
        """
        self.processing_latency.labels(topic=topic, event_type=event_type).observe(latency_seconds)
    
    def record_error(self, topic: str, event_type: str, error_type: str) -> None:
        """
        Record an error event.
        
        Args:
            topic: Topic name
            event_type: Event type
            error_type: Type of error (e.g., 'serialization', 'handler', 'connection')
        """
        self.errors.labels(topic=topic, event_type=event_type, error_type=error_type).inc()
    
    def increment_in_flight(self) -> None:
        """Increment in-flight message counter."""
        self.in_flight_messages.inc()
    
    def decrement_in_flight(self) -> None:
        """Decrement in-flight message counter."""
        self.in_flight_messages.dec()
    
    def get_metrics_summary(self) -> dict[str, any]:
        """
        Get summary of current metrics.
        
        Returns:
            Dictionary with metric summaries
        """
        # Note: This is a simplified summary. For full metrics, use /metrics endpoint
        return {
            'in_flight_messages': self.in_flight_messages._value.get(),
            'metrics_port': self.port,
            'server_started': self._server_started
        }
    
    @classmethod
    def reset_metrics(cls) -> None:
        """Reset class-level metrics state (useful for testing)."""
        cls._metrics_created = False
        cls._shared_metrics = {}
