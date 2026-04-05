from datetime import datetime, UTC
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlmodel import Session, select
from typing import List, Optional
from sqlalchemy import text

from app.database import get_session
from app.models import (
    ScanSession,
    ScanItem,
    LegoSet,
    Rental,
    User,
    RbInventory,
)
from app.schemas import (
    ScanSessionCreate,
    ScanSessionRead,
    ScanIdentifyResult,
    ScanIdentifyResponse,
    MarkBatchRequest,
)
from app.routers.auth import get_current_user
from app.ai_pipeline import identify_element
from app.color_mapping import (
    normalize_color_name,
    normalize_db_color,
)

router = APIRouter(prefix="/scan", tags=["scan"])


def _get_session_or_403(session_id: int, db: Session, current_user: User) -> ScanSession:
    scan_session = db.get(ScanSession, session_id)
    if not scan_session:
        raise HTTPException(status_code=404, detail="Session not found.")
    rental = db.get(Rental, scan_session.rental_id)
    if not rental or rental.renter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your session.")
    return scan_session


@router.post("/identify", response_model=ScanIdentifyResponse)
async def identify_part(
    session_id: int = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    scan_session = _get_session_or_403(session_id, db, current_user)

    if scan_session.status == "COMPLETE":
        raise HTTPException(status_code=400, detail="Session already complete.")

    scan_items = db.exec(
        select(ScanItem).where(ScanItem.session_id == session_id)
    ).all()

    session_parts = {}
    for item in scan_items:
        pn = item.part_num
        color = normalize_db_color(item.color)

        if pn not in session_parts:
            session_parts[pn] = set()

        if color:
            session_parts[pn].add(color)

    result = await identify_element(file, session_parts=session_parts)

    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    if not result.get("elements"):
        raise HTTPException(status_code=422, detail="No elements detected.")

    elements = [
        ScanIdentifyResult(
            part_num=e["elem_id"],
            color_name=e.get("color"),
            confidence=round(e["confidence"] / 100, 4),
            detection_confidence=round(e["detection_confidence"] / 100, 4),
            bounding_box=e["bounding_box"],
        )
        for e in result["elements"]
    ]
    return ScanIdentifyResponse(count=len(elements), elements=elements)


@router.post("/session", response_model=ScanSessionRead)
async def create_scan_session(
    data: ScanSessionCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    rental = db.get(Rental, data.rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found.")
    if rental.renter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your rental.")

    existing_incomplete = db.exec(
        select(ScanSession)
        .where(
            ScanSession.rental_id == data.rental_id,
            ScanSession.status == "INCOMPLETE",
        )
        .order_by(ScanSession.id.desc())
    ).first()

    if existing_incomplete:
        return existing_incomplete

    lego_set = db.get(LegoSet, data.lego_set_id)
    if not lego_set:
        raise HTTPException(status_code=404, detail="Lego set not found.")

    if not lego_set.set_num:
        raise HTTPException(status_code=400, detail="Lego set has no set_num.")

    inventory_stmt = (
        select(RbInventory)
        .where(RbInventory.set_num == lego_set.set_num)
        .order_by(RbInventory.version.desc())
    )
    inventory = db.exec(inventory_stmt).first()

    if not inventory:
        raise HTTPException(
            status_code=404,
            detail=f"No local Rebrickable inventory found for set {lego_set.set_num}"
        )

    scan_session = ScanSession(
        rental_id=data.rental_id,
        lego_set_id=data.lego_set_id,
        status="INCOMPLETE",
    )
    db.add(scan_session)
    db.commit()
    db.refresh(scan_session)

    parts_result = db.execute(text("""
        select
            ip.part_num,
            ip.quantity,
            p.name as part_name,
            c.name as color_name,
            ip.img_url
        from rb_inventory_parts ip
        join rb_parts p on p.part_num = ip.part_num
        join rb_colors c on c.id = ip.color_id
        where ip.inventory_id = :inventory_id
          and ip.is_spare = false
    """), {"inventory_id": inventory.id})

    rows = parts_result.all()

    if not rows:
        scan_session.status = "ERROR_PARTS_FETCH"
        db.add(scan_session)
        db.commit()
        raise HTTPException(
            status_code=404,
            detail=f"Inventory exists, but has no parts for set {lego_set.set_num}"
        )

    items = []
    for row in rows:
        normalized_color = normalize_color_name(row.color_name)
        for _ in range(row.quantity):
            items.append(
                ScanItem(
                    session_id=scan_session.id,
                    part_num=row.part_num,
                    name=row.part_name,
                    color=normalized_color,
                    img_url=row.img_url,
                    status="missing",
                )
            )

    db.add_all(items)
    db.commit()
    db.refresh(scan_session)
    return scan_session


@router.get("/session/{session_id}", response_model=ScanSessionRead)
def get_scan_session(
    session_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return _get_session_or_403(session_id, db, current_user)


@router.get("/rental/{rental_id}", response_model=List[ScanSessionRead])
def get_sessions_for_rental(
    rental_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    rental = db.get(Rental, rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found.")
    if rental.renter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your rental.")

    stmt = (
        select(ScanSession)
        .where(ScanSession.rental_id == rental_id)
        .order_by(ScanSession.id.desc())
    )
    return db.exec(stmt).all()


@router.get("/rental/{rental_id}/active-session", response_model=ScanSessionRead)
def get_active_session_for_rental(
    rental_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    rental = db.get(Rental, rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found.")
    if rental.renter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your rental.")

    active_session = db.exec(
        select(ScanSession)
        .where(
            ScanSession.rental_id == rental_id,
            ScanSession.status == "INCOMPLETE",
        )
        .order_by(ScanSession.id.desc())
    ).first()

    if not active_session:
        raise HTTPException(status_code=404, detail="No active session for this rental.")

    return active_session


@router.patch("/session/{session_id}/item/{part_num}", response_model=ScanSessionRead)
def mark_item_identified(
    session_id: int,
    part_num: str,
    confidence: float = 1.0,
    color_name: Optional[str] = None,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    scan_session = _get_session_or_403(session_id, db, current_user)

    if scan_session.status == "COMPLETE":
        raise HTTPException(status_code=400, detail="Session already complete.")

    stmt = select(ScanItem).where(
        ScanItem.session_id == session_id,
        ScanItem.part_num == part_num,
        ScanItem.status == "missing",
    )

    if color_name:
        normalized_color = normalize_color_name(color_name)
        stmt_with_color = stmt.where(ScanItem.color == normalized_color)
        item = db.exec(stmt_with_color).first()
        if not item:
            item = db.exec(stmt).first()
    else:
        item = db.exec(stmt).first()

    if not item:
        raise HTTPException(status_code=404, detail="Matching missing item not found.")

    item.status = "ai_identified"
    item.confidence = confidence
    db.add(item)

    remaining = db.exec(
        select(ScanItem).where(
            ScanItem.session_id == session_id,
            ScanItem.status == "missing",
        )
    ).first()

    if remaining is None:
        scan_session.status = "COMPLETE"
        db.add(scan_session)

    db.commit()
    db.refresh(scan_session)
    return scan_session


@router.patch("/session/{session_id}/item/{item_id}/confirm", response_model=ScanSessionRead)
def manual_confirm_item(
    session_id: int,
    item_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    scan_session = _get_session_or_403(session_id, db, current_user)

    if scan_session.status == "COMPLETE":
        raise HTTPException(status_code=400, detail="Session already complete.")

    item = db.exec(
        select(ScanItem).where(
            ScanItem.id == item_id,
            ScanItem.session_id == session_id,
            ScanItem.status == "missing",
        )
    ).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Item not found or already confirmed."
        )

    item.status = "manually_confirmed"
    item.confirmed_by = current_user.id
    item.confirmed_at = datetime.now(UTC)
    db.add(item)

    remaining = db.exec(
        select(ScanItem).where(
            ScanItem.session_id == session_id,
            ScanItem.status == "missing",
        )
    ).first()

    if remaining is None:
        scan_session.status = "COMPLETE"
        db.add(scan_session)

    db.commit()
    db.refresh(scan_session)
    return scan_session


@router.patch("/session/{session_id}/mark-batch", response_model=ScanSessionRead)
def mark_batch(
    session_id: int,
    body: MarkBatchRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    scan_session = _get_session_or_403(session_id, db, current_user)

    if scan_session.status == "COMPLETE":
        raise HTTPException(status_code=400, detail="Session already complete.")

    auto_identify_threshold = 0.50

    for element in body.elements:
        if element.confidence < auto_identify_threshold:
            continue

        stmt = select(ScanItem).where(
            ScanItem.session_id == session_id,
            ScanItem.part_num == element.part_num,
            ScanItem.status == "missing",
        )

        item = None

        if getattr(element, "color_name", None):
            normalized_color = normalize_color_name(element.color_name)
            if normalized_color:
                item = db.exec(
                    stmt.where(ScanItem.color == normalized_color)
                ).first()

        if not item:
            item = db.exec(stmt).first()

        if item:
            item.status = "ai_identified"
            item.confidence = element.confidence
            db.add(item)

    remaining = db.exec(
        select(ScanItem).where(
            ScanItem.session_id == session_id,
            ScanItem.status == "missing",
        )
    ).first()

    if remaining is None:
        scan_session.status = "COMPLETE"
        db.add(scan_session)

    db.commit()
    db.refresh(scan_session)
    return scan_session


@router.patch("/session/{session_id}/reset", response_model=ScanSessionRead)
def reset_scan_session(
    session_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    scan_session = _get_session_or_403(session_id, db, current_user)

    if scan_session.status == "COMPLETE":
        raise HTTPException(status_code=400, detail="Completed session cannot be reset.")

    items = db.exec(
        select(ScanItem).where(ScanItem.session_id == session_id)
    ).all()

    for item in items:
        item.status = "missing"
        item.confidence = None
        item.confirmed_by = None
        item.confirmed_at = None
        db.add(item)

    scan_session.status = "INCOMPLETE"
    db.add(scan_session)

    db.commit()
    db.refresh(scan_session)
    return scan_session


@router.patch("/session/{session_id}/finish", response_model=ScanSessionRead)
def finish_scan_session(
    session_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    scan_session = _get_session_or_403(session_id, db, current_user)

    if scan_session.status == "COMPLETE":
        raise HTTPException(status_code=400, detail="Session already complete.")

    scan_session.status = "COMPLETE"
    db.add(scan_session)

    db.commit()
    db.refresh(scan_session)
    return scan_session