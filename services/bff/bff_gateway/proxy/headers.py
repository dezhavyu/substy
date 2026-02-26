HOP_BY_HOP_HEADERS = {
    "host",
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def filter_request_headers(headers: dict[str, str]) -> dict[str, str]:
    safe = {}
    for k, v in headers.items():
        key = k.lower()
        if key in HOP_BY_HOP_HEADERS:
            continue
        safe[k] = v
    return safe
