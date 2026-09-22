from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.pond import Pond
from app.models.quarantine_dossier import QuarantineDossier
from app.models.user import User
from app.quarantine import evaluate_release, get_open_dossier, release_dossier
from app.schemas.quarantine_dossier import QuarantineDossierCreate, QuarantineDossierOut

router = APIRouter(prefix="/api/quarantine-dossiers", tags=["quarantine-dossiers"])


def to_out(db: Session, dossier: QuarantineDossier) -> QuarantineDossierOut:
    ev = evaluate_release(db, dossier)
    return QuarantineDossierOut(
        id=dossier.id,
        pond_id=dossier.pond_id,
        opened_at=dossier.opened_at,
        released_at=dossier.released_at,
        conclusion=dossier.conclusion,
        sample_count=ev.sample_count,
        latest_do_mg_l=ev.latest_do_mg_l,
        releasable=dossier.released_at is None and ev.ok,
    )


@router.get("", response_model=List[QuarantineDossierOut])
def list_dossiers(
    pond_id: Optional[int] = Query(None, alias="pondId"),
    open_only: Optional[bool] = Query(None, alias="open"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(QuarantineDossier)
    if pond_id is not None:
        q = q.filter(QuarantineDossier.pond_id == pond_id)
    if open_only:
        q = q.filter(QuarantineDossier.released_at.is_(None))
    return [to_out(db, d) for d in q.order_by(QuarantineDossier.id.desc()).all()]


@router.post("", response_model=QuarantineDossierOut, status_code=status.HTTP_201_CREATED)
def open_dossier(
    payload: QuarantineDossierCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    pond = db.query(Pond).filter(Pond.id == payload.pond_id).first()
    if not pond:
        raise HTTPException(status_code=400, detail="塘口不存在")
    if pond.status != "quarantine":
        raise HTTPException(status_code=400, detail="仅隔离塘可立案")
    if get_open_dossier(db, pond.id) is not None:
        raise HTTPException(status_code=409, detail="该塘口已存在未解除卷宗，同塘同时只许一份")
    item = QuarantineDossier(
        pond_id=pond.id,
        opened_at=payload.opened_at or datetime.now(timezone.utc),
        released_at=None,
        conclusion=payload.conclusion,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该塘口已存在未解除卷宗，同塘同时只许一份")
    db.refresh(item)
    return to_out(db, item)


@router.get("/{dossier_id}", response_model=QuarantineDossierOut)
def get_dossier(
    dossier_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = db.query(QuarantineDossier).filter(QuarantineDossier.id == dossier_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="卷宗不存在")
    return to_out(db, item)


@router.post("/{dossier_id}/release", response_model=QuarantineDossierOut)
def release(
    dossier_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = db.query(QuarantineDossier).filter(QuarantineDossier.id == dossier_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="卷宗不存在")
    release_dossier(db, item)
    db.commit()
    db.refresh(item)
    return to_out(db, item)
