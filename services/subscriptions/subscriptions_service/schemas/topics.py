from pydantic import BaseModel, ConfigDict, Field


class TopicCreateRequest(BaseModel):
    key: str = Field(min_length=2, max_length=128, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    name: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=2000)


class TopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    key: str
    name: str
    description: str | None


class TopicsListResponse(BaseModel):
    items: list[TopicResponse]
    next_cursor: str | None = None
