from datetime import datetime
from typing import List, Optional

from sqlalchemy import Integer, ForeignKey, DateTime, Text, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class QuarantineCase(Base):
    """检疫解除卷宗：隔离塘立案后，凭卷宗采样、达标后方可解除并改回在养。"""

    __tablename__ = "quarantine_cases"
    __table_args__ = (
        # 同塘同时只许一份未解除卷宗（部分唯一索引：仅约束 released_at 为空的行）
        Index(
            "uq_quarantine_cases_open_pond",
            "pond_id",
            unique=True,
            postgresql_where=text("released_at IS NULL"),
            sqlite_where=text("released_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pond_id: Mapped[int] = mapped_column(ForeignKey("ponds.id"), nullable=False, index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    pond: Mapped["Pond"] = relationship("Pond", back_populates="quarantine_cases")
    water_samples: Mapped[List["WaterSample"]] = relationship(
        "WaterSample", back_populates="quarantine_case"
    )
