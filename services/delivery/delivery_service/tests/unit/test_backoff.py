from delivery_service.core.backoff import compute_backoff_delay


def test_backoff_grows_exponentially_without_exceeding_max():
    base = 5
    max_delay = 60
    jitter = 0

    first = compute_backoff_delay(1, base, max_delay, jitter)
    second = compute_backoff_delay(2, base, max_delay, jitter)
    third = compute_backoff_delay(3, base, max_delay, jitter)
    huge = compute_backoff_delay(20, base, max_delay, jitter)

    assert first == 5
    assert second == 10
    assert third == 20
    assert huge == max_delay
