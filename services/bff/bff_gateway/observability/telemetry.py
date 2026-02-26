from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from bff_gateway.core.settings import Settings


_initialized = False


def configure_telemetry(settings: Settings, app) -> None:  # type: ignore[no-untyped-def]
    global _initialized
    if _initialized or not settings.otel_enabled:
        return

    provider = TracerProvider(resource=Resource(attributes={SERVICE_NAME: settings.otel_service_name}))
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
    )
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    _initialized = True
