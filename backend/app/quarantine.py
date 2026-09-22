"""检疫卷宗解除判定规则。

解除接口（POST /api/quarantine-cases/{id}/release）与塘口改状态接口
（PUT /api/ponds/{id}）共用本模块，保证「能否解除 / 能否改回在养」
只有一处判定逻辑，避免把解除做成随意改回在养的开关。
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.quarantine_case import QuarantineCase
from app.models.water_sample import WaterSample

# 解除硬性条件：卷宗下至少 3 份水质样，且最近一份溶氧 >= 5 mg/L
MIN_SAMPLES_FOR_RELEASE = 3
MIN_LATEST_DO_FOR_RELEASE = 5.0


@dataclass
class ReleaseEvaluation:
    case_id: int
    sample_count: int
    latest_do_mg_l: Optional[float]
    ok: bool
    reason: Optional[str]


def get_open_case(db: Session, pond_id: int) -> Optional[QuarantineCase]:
    """返回该塘口当前未解除的卷宗（同塘同时至多一份，由部分唯一索引保证）。"""
    return (
        db.query(QuarantineCase)
        .filter(
            QuarantineCase.pond_id == pond_id,
            QuarantineCase.released_at.is_(None),
        )
        .first()
    )


def evaluate_release(db: Session, case: QuarantineCase) -> ReleaseEvaluation:
    """判定卷宗是否满足解除条件（不改任何数据，只给结论）。"""
    samples = (
        db.query(WaterSample)
        .filter(WaterSample.case_id == case.id)
        .order_by(WaterSample.sampled_at.desc(), WaterSample.id.desc())
        .all()
    )
    count = len(samples)
    latest_do = samples[0].do_mg_l if samples else None

    if count < MIN_SAMPLES_FOR_RELEASE:
        return ReleaseEvaluation(
            case_id=case.id,
            sample_count=count,
            latest_do_mg_l=latest_do,
            ok=False,
            reason=f"卷宗水质样不足 {MIN_SAMPLES_FOR_RELEASE} 份（当前 {count} 份）",
        )
    if latest_do is None or latest_do < MIN_LATEST_DO_FOR_RELEASE:
        return ReleaseEvaluation(
            case_id=case.id,
            sample_count=count,
            latest_do_mg_l=latest_do,
            ok=False,
            reason=(
                f"最近一份水质样溶解氧 {latest_do} mg/L，"
                f"低于解除阈值 {MIN_LATEST_DO_FOR_RELEASE} mg/L"
            ),
        )
    return ReleaseEvaluation(
        case_id=case.id,
        sample_count=count,
        latest_do_mg_l=latest_do,
        ok=True,
        reason=None,
    )
