from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, status

from subscriptions_service.api.dependencies import get_topics_service
from subscriptions_service.core.dependencies import get_connection, get_current_roles
from subscriptions_service.schemas.topics import TopicCreateRequest, TopicResponse, TopicsListResponse
from subscriptions_service.services.topics import TopicsService

router = APIRouter(tags=["topics"])


@router.get("/topics", response_model=TopicsListResponse)
async def list_topics(
    q: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=50, ge=1, le=500),
    cursor: str | None = Query(default=None),
    conn: asyncpg.Connection = Depends(get_connection),
    service: TopicsService = Depends(get_topics_service),
) -> TopicsListResponse:
    topics, next_cursor = await service.list_topics(conn=conn, q=q, limit=limit, cursor=cursor)
    return TopicsListResponse(
        items=[
            TopicResponse(id=str(topic.id), key=topic.key, name=topic.name, description=topic.description)
            for topic in topics
        ],
        next_cursor=next_cursor,
    )


@router.get("/topics/{topic_id}", response_model=TopicResponse)
async def get_topic(
    topic_id: UUID,
    conn: asyncpg.Connection = Depends(get_connection),
    service: TopicsService = Depends(get_topics_service),
) -> TopicResponse:
    topic = await service.get_topic(conn=conn, topic_id=topic_id)
    return TopicResponse(id=str(topic.id), key=topic.key, name=topic.name, description=topic.description)


@router.post("/topics", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(
    payload: TopicCreateRequest,
    roles: set[str] = Depends(get_current_roles),
    conn: asyncpg.Connection = Depends(get_connection),
    service: TopicsService = Depends(get_topics_service),
) -> TopicResponse:
    topic = await service.create_topic(
        conn=conn,
        roles=roles,
        key=payload.key,
        name=payload.name,
        description=payload.description,
    )
    return TopicResponse(id=str(topic.id), key=topic.key, name=topic.name, description=topic.description)
