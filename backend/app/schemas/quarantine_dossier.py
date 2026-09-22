from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class QuarantineDossierCreate(BaseModel):
    pond_id: int = Field(..., alias="pondId")
    conclusion: str = Field(..., min_length=1, max_length=500)
    opened_at: Optional[datetime] = Field(None, alias="openedAt")

    model_config = ConfigDict(populate_by_name=True)


class QuarantineDossierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    pond_id: int = Field(serialization_alias="pondId")
    opened_at: datetime = Field(serialization_alias="openedAt")
    released_at: Optional[datetime] = Field(serialization_alias="releasedAt")
    conclusion: str
    sample_count: int = Field(serialization_alias="sampleCount")
    latest_do_mg_l: Optional[float] = Field(serialization_alias="latestDoMgL")
    releasable: bool
