"""检疫卷宗共享判定逻辑。

改塘口状态接口（routers/ponds.py）与卷宗解除接口
（routers/quarantine_dossiers.py）共用本模块，保证
「未解除卷宗 → 禁止回到在养」只有一份实现。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.pond import Pond
from app.models.quarantine_dossier import QuarantineDossier
from app.models.water_sample import WaterSample

# 解除条件：卷宗下至少 3 份水质样，且最近一份溶氧不低于 5 mg/L
MIN_RELEASE_SAMPLES = 3
MIN_RELEASE_DO_MG_L = 5.0


@dataclass
class ReleaseEvaluation:
    sample_count: int
    latest_do_mg_l: Optional[float]
    reasons: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.reasons


def get_open_dossier(db: Session, pond_id: int) -> Optional[QuarantineDossier]:
    """塘口当前未解除的卷宗（同塘同时至多一份，由部分唯一索引保证）。"""
    return (
        db.query(QuarantineDossier)
        .filter(
            QuarantineDossier.pond_id == pond_id,
            QuarantineDossier.released_at.is_(None),
        )
        .first()
    )


def evaluate_release(db: Session, dossier: QuarantineDossier) -> ReleaseEvaluation:
    """判定卷宗是否满足解除条件，不满足时给出全部原因。"""
    samples = (
        db.query(WaterSample)
        .filter(WaterSample.dossier_id == dossier.id)
        .order_by(WaterSample.sampled_at.desc(), WaterSample.id.desc())
        .all()
    )
    latest = samples[0] if samples else None
    ev = ReleaseEvaluation(
        sample_count=len(samples),
        latest_do_mg_l=latest.do_mg_l if latest else None,
    )
    if ev.sample_count < MIN_RELEASE_SAMPLES:
        ev.reasons.append(
            f"卷宗水质样不足 {MIN_RELEASE_SAMPLES} 份（当前 {ev.sample_count} 份）"
        )
    if latest is not None and latest.do_mg_l < MIN_RELEASE_DO_MG_L:
        ev.reasons.append(
            f"最近一份水质样溶氧 {latest.do_mg_l} mg/L 低于 {MIN_RELEASE_DO_MG_L} mg/L"
        )
    return ev


def apply_pond_status(db: Session, pond: Pond, new_status: str) -> None:
    """塘口状态变更的唯一入口。

    任何把塘口改为 stocked（在养）的路径都必须经过这里：
    存在未解除的检疫卷宗时一律 409，只能先走卷宗解除流程。
    """
    if new_status == "stocked" and pond.status != "stocked":
        dossier = get_open_dossier(db, pond.id)
        if dossier is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"塘口存在未解除的检疫卷宗 #{dossier.id}，"
                    "须先在检疫卷宗页完成解除，禁止直接改回在养"
                ),
            )
    pond.status = new_status


def release_dossier(db: Session, dossier: QuarantineDossier) -> QuarantineDossier:
    """解除卷宗：判定通过则写入解除时刻，并把塘口改回在养。"""
    if dossier.released_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"卷宗 #{dossier.id} 已解除，解除时刻不可重复写入",
        )
    ev = evaluate_release(db, dossier)
    if not ev.ok:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="；".join(ev.reasons) + "，解除时刻保持为空",
        )
    dossier.released_at = datetime.now(timezone.utc)
    # 先 flush 让解除时刻落库，get_open_dossier 才查不到本卷宗，
    # 共用函数 apply_pond_status 才会放行并改回在养
    db.flush()
    apply_pond_status(db, dossier.pond, "stocked")
    return dossier
