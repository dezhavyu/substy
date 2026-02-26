import random


def compute_backoff_delay(
    attempt_no: int,
    base_delay_seconds: int,
    max_delay_seconds: int,
    jitter_max_seconds: int,
) -> int:
    exp_delay = base_delay_seconds * (2 ** max(attempt_no - 1, 0))
    jitter = random.randint(0, max(jitter_max_seconds, 0))
    return min(exp_delay + jitter, max_delay_seconds)
