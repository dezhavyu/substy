from threading import Lock


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._http_total: dict[tuple[str, int], int] = {}
        self._http_duration_sum: dict[str, float] = {}
        self._http_duration_count: dict[str, int] = {}
        self._rate_limited = 0
        self._downstream_errors: dict[str, int] = {}

    def observe_http(self, route: str, status: int, duration_seconds: float) -> None:
        with self._lock:
            self._http_total[(route, status)] = self._http_total.get((route, status), 0) + 1
            self._http_duration_sum[route] = self._http_duration_sum.get(route, 0.0) + duration_seconds
            self._http_duration_count[route] = self._http_duration_count.get(route, 0) + 1

    def inc_rate_limited(self) -> None:
        with self._lock:
            self._rate_limited += 1

    def inc_downstream_error(self, service: str) -> None:
        with self._lock:
            self._downstream_errors[service] = self._downstream_errors.get(service, 0) + 1

    def render_prometheus(self) -> str:
        with self._lock:
            lines = [
                "# HELP http_requests_total Total HTTP requests",
                "# TYPE http_requests_total counter",
            ]
            for (route, status), count in sorted(self._http_total.items()):
                lines.append(f'http_requests_total{{route="{route}",status="{status}"}} {count}')

            lines.append("# HELP http_request_duration_seconds_sum HTTP duration sum")
            lines.append("# TYPE http_request_duration_seconds_sum counter")
            for route, value in sorted(self._http_duration_sum.items()):
                lines.append(f'http_request_duration_seconds_sum{{route="{route}"}} {value}')

            lines.append("# HELP http_request_duration_seconds_count HTTP duration count")
            lines.append("# TYPE http_request_duration_seconds_count counter")
            for route, value in sorted(self._http_duration_count.items()):
                lines.append(f'http_request_duration_seconds_count{{route="{route}"}} {value}')

            lines.append("# HELP rate_limited_requests_total Total rate limited requests")
            lines.append("# TYPE rate_limited_requests_total counter")
            lines.append(f"rate_limited_requests_total {self._rate_limited}")

            lines.append("# HELP downstream_errors_total Total downstream errors")
            lines.append("# TYPE downstream_errors_total counter")
            for service, value in sorted(self._downstream_errors.items()):
                lines.append(f'downstream_errors_total{{service="{service}"}} {value}')

        return "\n".join(lines) + "\n"
