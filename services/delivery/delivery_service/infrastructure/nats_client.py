import json
from typing import Any

import nats
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext
from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy, StreamConfig

from delivery_service.core.settings import Settings


class NATSClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: NATS | None = None
        self._jetstream: JetStreamContext | None = None

    async def startup(self) -> None:
        self._client = await nats.connect(
            servers=[self._settings.nats_url],
            connect_timeout=self._settings.nats_connect_timeout,
        )
        self._jetstream = self._client.jetstream()

        assert self._jetstream is not None
        stream_cfg = StreamConfig(
            name=self._settings.nats_stream_name,
            subjects=[
                self._settings.nats_subject_notification_created,
                self._settings.nats_subject_delivery_succeeded,
                self._settings.nats_subject_delivery_failed,
            ],
        )
        try:
            await self._jetstream.add_stream(stream_cfg)
        except Exception:
            await self._jetstream.update_stream(stream_cfg)

    async def ensure_consumer(self) -> None:
        if self._jetstream is None:
            raise RuntimeError("JetStream is not initialized")

        cfg = ConsumerConfig(
            durable_name=self._settings.nats_durable_name,
            ack_policy=AckPolicy.EXPLICIT,
            deliver_policy=DeliverPolicy.ALL,
            filter_subject=self._settings.nats_subject_notification_created,
        )
        try:
            await self._jetstream.add_consumer(self._settings.nats_stream_name, cfg)
        except Exception:
            return

    async def shutdown(self) -> None:
        if self._client and self._client.is_connected:
            await self._client.close()

    async def ping(self) -> None:
        if not self._client or not self._client.is_connected:
            raise RuntimeError("NATS is not connected")

    async def publish_json(self, subject: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> None:
        if self._jetstream is None:
            raise RuntimeError("JetStream is not initialized")
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        await self._jetstream.publish(subject, data, headers=headers or {})

    async def pull_subscribe(self, subject: str):  # type: ignore[no-untyped-def]
        if self._jetstream is None:
            raise RuntimeError("JetStream is not initialized")
        return await self._jetstream.pull_subscribe(
            subject=subject,
            durable=self._settings.nats_durable_name,
            stream=self._settings.nats_stream_name,
        )
