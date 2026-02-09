
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select


from app.database import get_session
from app.models import LegoSet, RebrickableSet, User, Rental
from app.schemas import LegoSetCreate, LegoSetRead, LegoSetUpdate
from app.routers.auth import get_current_user

from app.schemas import AvailabilityCreate, AvailabilityRead
from app.models import Availability

from fastapi import Query


router = APIRouter(
    prefix="/sets",
    tags=["sets"],
)

@router.post("/", response_model=LegoSetRead, status_code=status.HTTP_201_CREATED)
def create_lego_set(
    lego_set_in: LegoSetCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # 1) Kötelező: set_num vagy title
    if not lego_set_in.set_num and not lego_set_in.title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either set_num or title must be provided.",
        )

    # 2) Ha van set_num, próbáljuk betölteni a RebrickableSet-et
    rb_set = None
    number_of_items = None
    title = lego_set_in.title

    if lego_set_in.set_num:
        statement = select(RebrickableSet).where(
            RebrickableSet.set_num == lego_set_in.set_num
        )
        rb_set = db.exec(statement).one_or_none()
        if not rb_set:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rebrickable set not found for given set_num.",
            )
        number_of_items = rb_set.num_parts  # innen jön a number_of_items [web:25][web:42]
        if title is None:
            title = rb_set.name  # ha nem adott külön címet, használjuk a katalógus nevét [web:17]

    # 3) missing_items listából string
    missing_items_raw = None
    if lego_set_in.missing_items:
        missing_items_raw = ",".join(lego_set_in.missing_items)

    # 4) LegoSet példány létrehozása
    db_lego_set = LegoSet(
        set_num=lego_set_in.set_num if lego_set_in.set_num else "",
        title=title if title else "",
        location=lego_set_in.location,
        rental_price=lego_set_in.rental_price,
        deposit=lego_set_in.deposit,
        scan_required=lego_set_in.scan_required,
        state=lego_set_in.state,
        notes=lego_set_in.notes,
        public=lego_set_in.public,
        owner_id=current_user.id,
        number_of_items=number_of_items,
        missing_items_raw=missing_items_raw,
    )

    db.add(db_lego_set)
    db.commit()
    db.refresh(db_lego_set)

    # 5) Visszaalakítás LegoSetRead-be
    return LegoSetRead(
        id=db_lego_set.id,
        owner_id=db_lego_set.owner_id,
        created_at=db_lego_set.created_at,
        set_num=db_lego_set.set_num,
        title=db_lego_set.title,
        location=db_lego_set.location,
        rental_price=db_lego_set.rental_price,
        deposit=db_lego_set.deposit,
        scan_required=db_lego_set.scan_required,
        state=db_lego_set.state,
        notes=db_lego_set.notes,
        public=db_lego_set.public,
        number_of_items=db_lego_set.number_of_items,
        missing_items=(
            db_lego_set.missing_items_raw.split(",")
            if db_lego_set.missing_items_raw
            else None
        ),
    )

def add_availability_period(
    set_id: int,
    period: AvailabilityCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    lego_set = db.get(LegoSet, set_id)
    if not lego_set:
        raise HTTPException(status_code=404, detail="Lego set not found.")

    # csak a tulaj módosíthatja
    if lego_set.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the owner of this set.")

    if period.end_date < period.start_date:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date.")

    # (opcionális) ütközés ellenőrzés más availability-vel
    stmt = select(Availability).where(
        Availability.lego_set_id == set_id,
        Availability.start_date <= period.end_date,
        Availability.end_date >= period.start_date,
    )
    conflict = db.exec(stmt).first()
    if conflict:
        raise HTTPException(
            status_code=400,
            detail="Availability period overlaps with an existing one.",
        )

    availability = Availability(
        lego_set_id=set_id,
        start_date=period.start_date,
        end_date=period.end_date,
    )

    db.add(availability)
    db.commit()
    db.refresh(availability)

    return AvailabilityRead(
        id=availability.id,
        lego_set_id=availability.lego_set_id,
        start_date=availability.start_date,
        end_date=availability.end_date,
    )

@router.get("/", response_model=List[LegoSetRead])
def list_lego_sets(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),  # ha publikus böngészés is lesz, ezt később lazíthatjuk
    location: str | None = None,
    title: str | None = None,
):
    statement = select(LegoSet)

    if location:
        statement = statement.where(LegoSet.location == location)
    if title:
        statement = statement.where(LegoSet.title.ilike(f"%{title}%"))

    results = db.exec(statement).all()

    lego_sets_read: List[LegoSetRead] = []
    for s in results:
        lego_sets_read.append(
            LegoSetRead(
                id=s.id,
                owner_id=s.owner_id,
                created_at=s.created_at,
                set_num=s.set_num,
                title=s.title,
                location=s.location,
                rental_price=s.rental_price,
                deposit=s.deposit,
                scan_required=s.scan_required,
                state=s.state,
                notes=s.notes,
                public=s.public,
                number_of_items=s.number_of_items,
                missing_items=(
                    s.missing_items_raw.split(",") if s.missing_items_raw else None
                ),
            )
        )
    return lego_sets_read

@router.get("/{set_id}", response_model=LegoSetRead)
def get_lego_set(
    set_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    lego_set = db.get(LegoSet, set_id)
    if not lego_set:
        raise HTTPException(status_code=404, detail="Lego set not found.")

    return LegoSetRead(
        id=lego_set.id,
        owner_id=lego_set.owner_id,
        created_at=lego_set.created_at,
        set_num=lego_set.set_num,
        title=lego_set.title,
        location=lego_set.location,
        rental_price=lego_set.rental_price,
        deposit=lego_set.deposit,
        scan_required=lego_set.scan_required,
        state=lego_set.state,
        notes=lego_set.notes,
        public=lego_set.public,
        number_of_items=lego_set.number_of_items,
        missing_items=(
            lego_set.missing_items_raw.split(",")
            if lego_set.missing_items_raw
            else None
        ),
    )

@router.put("/{set_id}", response_model=LegoSetRead)
def update_lego_set(
    set_id: int,
    updates: LegoSetUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    lego_set = db.get(LegoSet, set_id)
    if not lego_set:
        raise HTTPException(status_code=404, detail="Lego set not found.")

    if lego_set.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not the owner of this set.")

    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lego_set, field, value)

    db.add(lego_set)
    db.commit()
    db.refresh(lego_set)

    # itt használd a már meglévő LegoSetRead-be csomagoló logikádat
    return LegoSetRead(
        id=lego_set.id,
        owner_id=lego_set.owner_id,
        created_at=lego_set.created_at,
        set_num=lego_set.set_num,
        title=lego_set.title,
        location=lego_set.location,
        rental_price=lego_set.rental_price,
        deposit=lego_set.deposit,
        scan_required=lego_set.scan_required,
        state=lego_set.state,
        notes=lego_set.notes,
        public=lego_set.public,
        number_of_items=lego_set.number_of_items,
        missing_items=(
            lego_set.missing_items_raw.split(",")
            if getattr(lego_set, "missing_items_raw", None)
            else None
        ),
    )

@router.delete("/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lego_set(
    set_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    lego_set = db.get(LegoSet, set_id)
    if not lego_set:
        raise HTTPException(status_code=404, detail="Lego set not found.")

    is_owner = lego_set.owner_id == current_user.id
    is_admin = current_user.role == "ADMIN"

    if not (is_owner or is_admin):
        raise HTTPException(status_code=403, detail="Not allowed to delete this set.")

    # aktív rental ellenőrzés – igazítsd a status értékekhez, ha már enum
    active_statuses = ["REQUESTED", "ACCEPTED", "IN_PROGRESS", "RETURN_PENDING", "ACTIVE"]
    statement = select(Rental).where(
        Rental.lego_set_id == set_id,
        Rental.status.in_(active_statuses),
    )
    active_rental = db.exec(statement).first()
    if active_rental:
        raise HTTPException(
            status_code=400,
            detail="Set has active rentals; cannot delete.",
        )

    db.delete(lego_set)
    db.commit()
    return
@router.get("/", response_model=List[LegoSetRead])
def list_lego_sets(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    keyword: str | None = None,
    location: str | None = None,
    state: str | None = None,      # vagy LegoSetState | None
    public: bool = True,           # default: csak publikus
    limit: int = Query(default=20, le=100),
    offset: int = 0,
):
    statement = select(LegoSet)

    if public:
        statement = statement.where(LegoSet.public == True)  # noqa: E712

    if location:
        statement = statement.where(LegoSet.location == location)

    if state:
        statement = statement.where(LegoSet.state == state)

    if keyword:
        like = f"%{keyword}%"
        statement = statement.where(LegoSet.title.ilike(like))

    statement = statement.offset(offset).limit(limit)

    results = db.exec(statement).all()

    response: List[LegoSetRead] = []
    for s in results:
        response.append(
            LegoSetRead(
                id=s.id,
                owner_id=s.owner_id,
                created_at=s.created_at,
                set_num=s.set_num,
                title=s.title,
                location=s.location,
                rental_price=s.rental_price,
                deposit=s.deposit,
                scan_required=s.scan_required,
                state=s.state,
                notes=s.notes,
                public=s.public,
                number_of_items=s.number_of_items,
                missing_items=(
                    s.missing_items_raw.split(",") if s.missing_items_raw else None
                ),
            )
        )
    return response