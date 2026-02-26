from threading import Lock


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self.delivery_attempts_created_total: dict[str, int] = {}
        self.delivery_sent_total = 0
        self.delivery_failed_total = 0
        self.delivery_dead_total = 0
        self.delivery_delayed_quiet_hours_total: dict[str, int] = {}
        self.delivery_delay_seconds_sum = 0.0
        self.delivery_delay_seconds_count = 0
        self.subscriptions_fetch_latency_seconds_sum = 0.0
        self.subscriptions_fetch_latency_seconds_count = 0
        self.jetstream_messages_processed_total = 0

    def inc_attempts_created(self, channel: str, value: int = 1) -> None:
        if value <= 0:
            return
        with self._lock:
            self.delivery_attempts_created_total[channel] = (
                self.delivery_attempts_created_total.get(channel, 0) + value
            )

    def inc_sent(self) -> None:
        with self._lock:
            self.delivery_sent_total += 1

    def inc_failed(self) -> None:
        with self._lock:
            self.delivery_failed_total += 1

    def inc_dead(self) -> None:
        with self._lock:
            self.delivery_dead_total += 1

    def inc_delayed_quiet_hours(self, channel: str) -> None:
        with self._lock:
            self.delivery_delayed_quiet_hours_total[channel] = (
                self.delivery_delayed_quiet_hours_total.get(channel, 0) + 1
            )

    def observe_delivery_delay(self, seconds: float) -> None:
        if seconds < 0:
            seconds = 0.0
        with self._lock:
            self.delivery_delay_seconds_sum += seconds
            self.delivery_delay_seconds_count += 1

    def observe_subscriptions_fetch_latency(self, seconds: float) -> None:
        with self._lock:
            self.subscriptions_fetch_latency_seconds_sum += seconds
            self.subscriptions_fetch_latency_seconds_count += 1

    def inc_jetstream_processed(self) -> None:
        with self._lock:
            self.jetstream_messages_processed_total += 1

    def render_prometheus(self) -> str:
        with self._lock:
            lines = [
                "# HELP delivery_attempts_created_total Total created delivery attempts",
                "# TYPE delivery_attempts_created_total counter",
            ]

            if self.delivery_attempts_created_total:
                for channel, value in sorted(self.delivery_attempts_created_total.items()):
                    lines.append(
                        f'delivery_attempts_created_total{{channel="{channel}"}} {value}'
                    )
            else:
                lines.append('delivery_attempts_created_total{channel="unknown"} 0')

            lines.extend(
                [
                    "# HELP delivery_sent_total Total successful deliveries",
                    "# TYPE delivery_sent_total counter",
                    f"delivery_sent_total {self.delivery_sent_total}",
                    "# HELP delivery_failed_total Total failed delivery retries",
                    "# TYPE delivery_failed_total counter",
                    f"delivery_failed_total {self.delivery_failed_total}",
                    "# HELP delivery_dead_total Total dead delivery attempts",
                    "# TYPE delivery_dead_total counter",
                    f"delivery_dead_total {self.delivery_dead_total}",
                    "# HELP delivery_delayed_quiet_hours_total Total attempts delayed due to quiet hours",
                    "# TYPE delivery_delayed_quiet_hours_total counter",
                ]
            )

            if self.delivery_delayed_quiet_hours_total:
                for channel, value in sorted(self.delivery_delayed_quiet_hours_total.items()):
                    lines.append(
                        f'delivery_delayed_quiet_hours_total{{channel="{channel}"}} {value}'
                    )
            else:
                lines.append('delivery_delayed_quiet_hours_total{channel="unknown"} 0')

            lines.extend(
                [
                    "# HELP delivery_delay_seconds_sum Sum of delay seconds before next delivery attempt",
                    "# TYPE delivery_delay_seconds_sum counter",
                    f"delivery_delay_seconds_sum {self.delivery_delay_seconds_sum}",
                    "# HELP delivery_delay_seconds_count Count of observed delivery delays",
                    "# TYPE delivery_delay_seconds_count counter",
                    f"delivery_delay_seconds_count {self.delivery_delay_seconds_count}",
                    "# HELP subscriptions_fetch_latency_seconds_sum Subscriptions fetch latency sum",
                    "# TYPE subscriptions_fetch_latency_seconds_sum counter",
                    f"subscriptions_fetch_latency_seconds_sum {self.subscriptions_fetch_latency_seconds_sum}",
                    "# HELP subscriptions_fetch_latency_seconds_count Subscriptions fetch latency count",
                    "# TYPE subscriptions_fetch_latency_seconds_count counter",
                    f"subscriptions_fetch_latency_seconds_count {self.subscriptions_fetch_latency_seconds_count}",
                    "# HELP jetstream_messages_processed_total Total processed JetStream messages",
                    "# TYPE jetstream_messages_processed_total counter",
                    f"jetstream_messages_processed_total {self.jetstream_messages_processed_total}",
                ]
            )

        return "\n".join(lines) + "\n"
