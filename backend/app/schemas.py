"""Pydantic 请求/响应模型。"""
from typing import Optional

from pydantic import BaseModel, Field


class DatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    chunk_size: int = Field(500, ge=50, le=4000)
    chunk_overlap: int = Field(50, ge=0, le=500)


class DatasetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    chunk_size: Optional[int] = Field(None, ge=50, le=4000)
    chunk_overlap: Optional[int] = Field(None, ge=0, le=500)


class SegmentCreate(BaseModel):
    content: str = Field(..., min_length=1)


class SegmentUpdate(BaseModel):
    content: Optional[str] = None
    enabled: Optional[bool] = None


class HitTestRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(4, ge=1, le=20)
    score_threshold: float = Field(0.0, ge=0.0, le=1.0)
