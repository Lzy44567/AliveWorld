"""Request contract shared by the workshop review endpoints."""
from typing import Literal
from pydantic import BaseModel, Field


class ReviewPayload(BaseModel):
    source: Literal['proposed', 'pending']
    operation_ids: list[str] = Field(min_length=1)
    accept: bool


class CreativeBriefPayload(BaseModel):
    creative_brief: str = Field(max_length=2000)
