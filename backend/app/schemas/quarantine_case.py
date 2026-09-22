from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.water_sample import WaterSampleOut


class QuarantineCaseCreate(BaseModel):
    pond_id: int = Field(..., alias="pondId")
    summary: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class QuarantineCaseRelease(BaseModel):
    summary: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class QuarantineCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    pond_id: int = Field(serialization_alias="pondId")
    opened_at: datetime = Field(serialization_alias="openedAt")
    released_at: Optional[datetime] = Field(serialization_alias="releasedAt")
    summary: Optional[str] = None
    sample_count: int = Field(serialization_alias="sampleCount")


class QuarantineCaseDetail(QuarantineCaseOut):
    samples: List[WaterSampleOut] = []
