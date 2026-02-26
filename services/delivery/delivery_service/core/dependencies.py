from fastapi import Request

from delivery_service.core.container import Container


def get_container(request: Request) -> Container:
    return request.app.state.container
