from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session, select
from typing import List
import random

from app.database import get_session
from app.models import ScanSession, ScanItem, LegoSet, Rental, User
from app.schemas import ScanSessionCreate, ScanSessionRead, ScanIdentifyResult
from app.routers.auth import get_current_user

router = APIRouter(prefix="/scan", tags=["scan"])


@router.post("/identify", response_model=ScanIdentifyResult)
async def identify_part(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Kép alapján azonosítja a LEGO elemet.
    Egyelőre mock – az AI service integrációja később kerül ide.
    """
    # TODO: kép továbbítása az AI microservice-nek
    # Egyelőre mock válasz
    mock_parts = ["3001", "3003", "3004", "3010", "3020", "3021", "3022", "3023"]
    return ScanIdentifyResult(
        part_num=random.choice(mock_parts),
        confidence=round(random.uniform(0.75, 0.99), 2),
    )


@router.post("/session", response_model=ScanSessionRead)
def create_scan_session(
    data: ScanSessionCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Új scan session létrehozása egy rental-hoz."""
    # Rental ellenőrzés
    rental = db.get(Rental, data.rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found.")
    if rental.renter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your rental.")

    # LegoSet elemlistájának lekérése
    lego_set = db.get(LegoSet, data.lego_set_id)
    if not lego_set:
        raise HTTPException(status_code=404, detail="Lego set not found.")

    # Session létrehozása
    session = ScanSession(
        rental_id=data.rental_id,
        lego_set_id=data.lego_set_id,
        status="INCOMPLETE",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # ScanItem-ek létrehozása az elemlistából
    if lego_set.missing_items_raw:
        parts = lego_set.missing_items_raw.split(",")
        for part_num in parts:
            item = ScanItem(
                session_id=session.id,
                part_num=part_num.strip(),
                identified=False,
            )
            db.add(item)
        db.commit()

    db.refresh(session)
    return session


@router.patch("/session/{session_id}/item/{part_num}", response_model=ScanSessionRead)
def mark_item_identified(
    session_id: int,
    part_num: str,
    confidence: float = 1.0,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Egy elem megtaláltnak jelölése a scan session-ben."""
    session = db.get(ScanSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Elem keresése
    stmt = select(ScanItem).where(
        ScanItem.session_id == session_id,
        ScanItem.part_num == part_num,
    )
    item = db.exec(stmt).first()
    if not item:
        raise HTTPException(status_code=404, detail="Part not found in session.")

    item.identified = True
    item.confidence = confidence
    db.add(item)

    # Ha minden elem megvan → COMPLETE
    all_items = db.exec(
        select(ScanItem).where(ScanItem.session_id == session_id)
    ).all()
    if all(i.identified for i in all_items):
        session.status = "COMPLETE"
        db.add(session)

    db.commit()
    db.refresh(session)
    return session


@router.get("/session/{session_id}", response_model=ScanSessionRead)
def get_scan_session(
    session_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    session = db.get(ScanSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@router.get("/rental/{rental_id}", response_model=List[ScanSessionRead])
def get_sessions_for_rental(
    rental_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Egy rental összes scan session-je."""
    stmt = select(ScanSession).where(ScanSession.rental_id == rental_id)
    return db.exec(stmt).all()

