from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.pond import Pond
from app.models.quarantine_case import QuarantineCase
from app.models.user import User
from app.models.water_sample import WaterSample
from app.quarantine import evaluate_release, get_open_case
from app.schemas.quarantine_case import (
    QuarantineCaseCreate,
    QuarantineCaseDetail,
    QuarantineCaseOut,
    QuarantineCaseRelease,
)
from app.schemas.water_sample import WaterSampleOut

router = APIRouter(prefix="/api/quarantine-cases", tags=["quarantine-cases"])


def _sample_count(db: Session, case_id: int) -> int:
    return db.query(WaterSample).filter(WaterSample.case_id == case_id).count()


def _to_out(db: Session, case: QuarantineCase) -> QuarantineCaseOut:
    return QuarantineCaseOut(
        id=case.id,
        pond_id=case.pond_id,
        opened_at=case.opened_at,
        released_at=case.released_at,
        summary=case.summary,
        sample_count=_sample_count(db, case.id),
    )


@router.get("", response_model=List[QuarantineCaseOut])
def list_cases(
    pond_id: Optional[int] = Query(None, alias="pondId"),
    open_only: bool = Query(False, alias="openOnly"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(QuarantineCase)
    if pond_id is not None:
        q = q.filter(QuarantineCase.pond_id == pond_id)
    if open_only:
        q = q.filter(QuarantineCase.released_at.is_(None))
    return [_to_out(db, c) for c in q.order_by(QuarantineCase.id.desc()).all()]


@router.post("", response_model=QuarantineCaseOut, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: QuarantineCaseCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    pond = db.query(Pond).filter(Pond.id == payload.pond_id).first()
    if not pond:
        raise HTTPException(status_code=400, detail="塘口不存在")
    if pond.status != "quarantine":
        raise HTTPException(status_code=400, detail="仅隔离塘可立案检疫卷宗")
    if get_open_case(db, pond.id) is not None:
        raise HTTPException(status_code=409, detail="该塘口已存在未解除的检疫卷宗")
    item = QuarantineCase(
        pond_id=pond.id,
        opened_at=datetime.now(timezone.utc),
        released_at=None,
        summary=payload.summary,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该塘口已存在未解除的检疫卷宗")
    db.refresh(item)
    return _to_out(db, item)


@router.get("/{case_id}", response_model=QuarantineCaseDetail)
def get_case(
    case_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    case = db.query(QuarantineCase).filter(QuarantineCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="检疫卷宗不存在")
    samples = (
        db.query(WaterSample)
        .filter(WaterSample.case_id == case.id)
        .order_by(WaterSample.sampled_at.desc(), WaterSample.id.desc())
        .all()
    )
    out = _to_out(db, case)
    return QuarantineCaseDetail(
        **out.model_dump(),
        samples=[WaterSampleOut.model_validate(s) for s in samples],
    )


@router.post("/{case_id}/release", response_model=QuarantineCaseOut)
def release_case(
    case_id: int,
    payload: Optional[QuarantineCaseRelease] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    case = db.query(QuarantineCase).filter(QuarantineCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="检疫卷宗不存在")
    if case.released_at is not None:
        raise HTTPException(status_code=409, detail="卷宗已解除，请勿重复操作")

    evaluation = evaluate_release(db, case)
    if not evaluation.ok:
        # 解除失败：released_at 保持为空，卷宗仍未解除
        raise HTTPException(status_code=409, detail=f"解除条件未满足：{evaluation.reason}")

    if payload and payload.summary:
        case.summary = payload.summary
    case.released_at = datetime.now(timezone.utc)

    pond = db.query(Pond).filter(Pond.id == case.pond_id).first()
    if pond:
        pond.status = "stocked"
    db.commit()
    db.refresh(case)
    return _to_out(db, case)
