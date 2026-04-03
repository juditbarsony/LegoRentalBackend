from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlmodel import Session, select
from typing import List
import httpx
from typing import Optional, List
from app.config import REBRICKABLE_API_KEY
from app.database import get_session
from app.models import ScanSession, ScanItem, LegoSet, Rental, User
from app.schemas import ScanSessionCreate, ScanSessionRead, ScanIdentifyResult, ScanIdentifyResponse, MarkBatchRequest 
from app.routers.auth import get_current_user
from app.ai_pipeline import identify_element



router = APIRouter(prefix="/scan", tags=["scan"])


# ==========================================
# SEGÉDFÜGGVÉNY: session tulajdonosának ellenőrzése
# ==========================================
def _get_session_or_403(session_id: int, db: Session, current_user: User) -> ScanSession:
    scan_session = db.get(ScanSession, session_id)
    if not scan_session:
        raise HTTPException(status_code=404, detail="Session not found.")
    rental = db.get(Rental, scan_session.rental_id)
    if not rental or rental.renter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your session.")
    return scan_session


# ==========================================
# POST /scan/identify — AI elemfelismerés (egyelőre mock)
# ==========================================
@router.post("/identify", response_model=ScanIdentifyResponse)
async def identify_part(
    session_id: int = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    
    # Session part lista lekérése DB-ből
    scan_items = db.exec(
        select(ScanItem).where(ScanItem.session_id == session_id)
    ).all()
    
    # {part_num: {color_normalized, ...}} szótár építése
    session_parts = {}
    for item in scan_items:
        pn = item.part_num
        color = item.color.strip().lower().replace(" ", "_") if item.color else None
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


# ==========================================
# POST /scan/session — Új scan session létrehozása
# ==========================================
@router.post("/session", response_model=ScanSessionRead)
async def create_scan_session(
    data: ScanSessionCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # Rental ellenőrzés
    rental = db.get(Rental, data.rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found.")
    if rental.renter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your rental.")

    # LegoSet ellenőrzés
    lego_set = db.get(LegoSet, data.lego_set_id)
    if not lego_set:
        raise HTTPException(status_code=404, detail="Lego set not found.")

    # Session létrehozása
    scan_session = ScanSession(
        rental_id=data.rental_id,
        lego_set_id=data.lego_set_id,
        status="INCOMPLETE",
    )
    db.add(scan_session)
    db.commit()
    db.refresh(scan_session)

    # Rebrickable API-ból elemek lekérése
    if lego_set.set_num:
        url = f"https://rebrickable.com/api/v3/lego/sets/{lego_set.set_num}/parts/"
        params = {"key": REBRICKABLE_API_KEY, "page_size": 1000}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)

        if response.status_code != 200:
            # Session megmaradt, de jelezzük, hogy az elemek nem töltődtek be
            scan_session.status = "ERROR_PARTS_FETCH"
            db.add(scan_session)
            db.commit()
            raise HTTPException(
                status_code=502,
                detail=f"Rebrickable API error: {response.status_code}"
            )

        parts_data = response.json().get("results", [])

        # ✅ Összes item egyszerre, egyetlen commit
        items = [
            ScanItem(
                session_id=scan_session.id,
                part_num=p["part"]["part_num"],
                name=p["part"]["name"],
                color=p["color"]["name"],
                status="missing",  # ← identified=False helyett
            )
            for p in parts_data
            for _ in range(p["quantity"])
        ]
        db.add_all(items)
        db.commit()

    db.refresh(scan_session)
    return scan_session


# ==========================================
# PATCH /scan/session/{session_id}/item/{part_num} — Elem megtaláltnak jelölése
# ==========================================
@router.patch("/session/{session_id}/item/{part_num}", response_model=ScanSessionRead)
def mark_item_identified(
    session_id: int,
    part_num: str,
    confidence: float = 1.0,
    color_name: Optional[str] = None,   # ← ÚJ
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
    # Ha van szín info → precíz egyezés; ha nincs → első találat
    if color_name:
        stmt_with_color = stmt.where(ScanItem.color == color_name)
        item = db.exec(stmt_with_color).first()
        if not item:
            # Fallback: szín nélkül próbálja (pl. ha a DB-ben más névformátum van)
            item = db.exec(stmt).first()
    else:
        item = db.exec(stmt).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Part not found or all instances already identified."
        )

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


# ==========================================
# GET /scan/session/{session_id} — Session lekérése
# ==========================================
@router.get("/session/{session_id}", response_model=ScanSessionRead)
def get_scan_session(
    session_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return _get_session_or_403(session_id, db, current_user)


# ==========================================
# GET /scan/rental/{rental_id} — Rental összes sessionje
# ==========================================
@router.get("/rental/{rental_id}", response_model=List[ScanSessionRead])
def get_sessions_for_rental(
    rental_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Egy rental összes scan sessionje — csak a saját rentalhoz."""
    rental = db.get(Rental, rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found.")
    if rental.renter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your rental.")

    stmt = select(ScanSession).where(ScanSession.rental_id == rental_id)
    return db.exec(stmt).all()


@router.post("/session/{session_id}/mark-batch", response_model=ScanSessionRead)
def mark_batch(
    session_id: int,
    body: MarkBatchRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    scan_session = _get_session_or_403(session_id, db, current_user)

    if scan_session.status == "COMPLETE":
        raise HTTPException(status_code=400, detail="Session already complete.")

    for element in body.elements:
        stmt = select(ScanItem).where(
            ScanItem.session_id == session_id,
            ScanItem.part_num == element.part_num,
            ScanItem.status == "missing",
        )
        if element.color_name:
            stmt_color = stmt.where(ScanItem.color == element.color_name)
            item = db.exec(stmt_color).first() or db.exec(stmt).first()
        else:
            item = db.exec(stmt).first()

        if item:
            item.status = "ai_identified"
            item.confidence = element.confidence
            db.add(item)

    remaining = db.exec(
        select(ScanItem).where(
            ScanItem.session_id == session_id,
            ScanItem.identified == False,
        )
    ).first()
    if remaining is None:
        scan_session.status = "COMPLETE"
        db.add(scan_session)

    db.commit()
    db.refresh(scan_session)
    return scan_session

