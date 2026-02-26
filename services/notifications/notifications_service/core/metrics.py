from dataclasses import dataclass
from threading import Lock
from time import perf_counter


@dataclass
class Timer:
    started_at: float


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self.notifications_created_total = 0
        self.outbox_unpublished_count = 0
        self.outbox_publish_attempts_total = 0
        self.outbox_publish_failures_total = 0
        self.outbox_publish_latency_sum = 0.0
        self.outbox_publish_latency_count = 0

        self.scheduler_picked_total = 0
        self.scheduler_tick_duration_sum = 0.0
        self.scheduler_tick_duration_count = 0
        self.scheduled_backlog_count = 0
        self.scheduled_due_count = 0

    def inc_notifications_created(self) -> None:
        with self._lock:
            self.notifications_created_total += 1

    def set_outbox_unpublished_count(self, value: int) -> None:
        with self._lock:
            self.outbox_unpublished_count = value

    def start_timer(self) -> Timer:
        return Timer(started_at=perf_counter())

    def observe_outbox_publish_latency(self, timer: Timer, failed: bool) -> None:
        duration = perf_counter() - timer.started_at
        with self._lock:
            self.outbox_publish_attempts_total += 1
            self.outbox_publish_latency_sum += duration
            self.outbox_publish_latency_count += 1
            if failed:
                self.outbox_publish_failures_total += 1

    def inc_scheduler_picked(self, count: int) -> None:
        if count <= 0:
            return
        with self._lock:
            self.scheduler_picked_total += count

    def observe_scheduler_tick_duration(self, timer: Timer) -> None:
        duration = perf_counter() - timer.started_at
        with self._lock:
            self.scheduler_tick_duration_sum += duration
            self.scheduler_tick_duration_count += 1

    def set_scheduled_counts(self, backlog_count: int, due_count: int) -> None:
        with self._lock:
            self.scheduled_backlog_count = backlog_count
            self.scheduled_due_count = due_count

    def render_prometheus(self) -> str:
        with self._lock:
            lines = [
                "# HELP notifications_created_total Total created notifications",
                "# TYPE notifications_created_total counter",
                f"notifications_created_total {self.notifications_created_total}",
                "# HELP outbox_unpublished_count Current number of unpublished outbox events",
                "# TYPE outbox_unpublished_count gauge",
                f"outbox_unpublished_count {self.outbox_unpublished_count}",
                "# HELP outbox_publish_attempts_total Total outbox publish attempts",
                "# TYPE outbox_publish_attempts_total counter",
                f"outbox_publish_attempts_total {self.outbox_publish_attempts_total}",
                "# HELP outbox_publish_failures_total Total outbox publish failures",
                "# TYPE outbox_publish_failures_total counter",
                f"outbox_publish_failures_total {self.outbox_publish_failures_total}",
                "# HELP outbox_publish_latency_seconds_sum Sum of outbox publish latency seconds",
                "# TYPE outbox_publish_latency_seconds_sum counter",
                f"outbox_publish_latency_seconds_sum {self.outbox_publish_latency_sum}",
                "# HELP outbox_publish_latency_seconds_count Count of outbox publish latency observations",
                "# TYPE outbox_publish_latency_seconds_count counter",
                f"outbox_publish_latency_seconds_count {self.outbox_publish_latency_count}",
                "# HELP scheduler_picked_total Total scheduled notifications moved to queued",
                "# TYPE scheduler_picked_total counter",
                f"scheduler_picked_total {self.scheduler_picked_total}",
                "# HELP scheduler_tick_duration_seconds_sum Sum of scheduler tick durations",
                "# TYPE scheduler_tick_duration_seconds_sum counter",
                f"scheduler_tick_duration_seconds_sum {self.scheduler_tick_duration_sum}",
                "# HELP scheduler_tick_duration_seconds_count Count of scheduler tick durations",
                "# TYPE scheduler_tick_duration_seconds_count counter",
                f"scheduler_tick_duration_seconds_count {self.scheduler_tick_duration_count}",
                "# HELP scheduled_backlog_count Number of scheduled notifications",
                "# TYPE scheduled_backlog_count gauge",
                f"scheduled_backlog_count {self.scheduled_backlog_count}",
                "# HELP scheduled_due_count Number of due scheduled notifications",
                "# TYPE scheduled_due_count gauge",
                f"scheduled_due_count {self.scheduled_due_count}",
            ]
        return "\n".join(lines) + "\n"
