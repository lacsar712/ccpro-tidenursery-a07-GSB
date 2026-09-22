from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.pond import Pond
from app.models.user import User
from app.models.water_sample import WaterSample
from app.quarantine import get_open_dossier
from app.schemas.water_sample import WaterSampleCreate, WaterSampleOut

router = APIRouter(prefix="/api/water-samples", tags=["water-samples"])


@router.get("", response_model=List[WaterSampleOut])
def list_samples(
    pond_id: Optional[int] = Query(None, alias="pondId"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(WaterSample)
    if pond_id is not None:
        q = q.filter(WaterSample.pond_id == pond_id)
    return q.order_by(WaterSample.sampled_at.desc()).all()


@router.post("", response_model=WaterSampleOut, status_code=status.HTTP_201_CREATED)
def create_sample(
    payload: WaterSampleCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    pond = db.query(Pond).filter(Pond.id == payload.pond_id).first()
    if not pond:
        raise HTTPException(status_code=400, detail="塘口不存在")
    dossier = get_open_dossier(db, pond.id)
    if dossier is not None:
        if payload.dossier_id is None:
            raise HTTPException(
                status_code=400,
                detail=f"该塘口有未解除的检疫卷宗 #{dossier.id}，新增水质样必须挂到该卷宗（dossierId）",
            )
        if payload.dossier_id != dossier.id:
            raise HTTPException(
                status_code=400,
                detail=f"dossierId 须为该塘口未解除卷宗 #{dossier.id}",
            )
    elif payload.dossier_id is not None:
        raise HTTPException(status_code=400, detail="该塘口当前没有未解除的检疫卷宗，不应关联 dossierId")
    item = WaterSample(
        pond_id=payload.pond_id,
        dossier_id=dossier.id if dossier is not None else None,
        sampled_at=payload.sampled_at,
        temp_c=payload.temp_c,
        salinity_ppt=payload.salinity_ppt,
        do_mg_l=payload.do_mg_l,
        ph=payload.ph,
        notes=payload.notes,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{sample_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sample(
    sample_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = db.query(WaterSample).filter(WaterSample.id == sample_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="水质样不存在")
    db.delete(item)
    db.commit()
