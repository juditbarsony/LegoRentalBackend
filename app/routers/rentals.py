from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from datetime import date, datetime
from typing import List

from app.database import get_session
from app.models import Rental, LegoSet, Availability, User
from app.schemas import RentalCreate, RentalRead
from app.routers.auth import get_current_user
from app.enums import RentalStatus

router = APIRouter(
    prefix="/rentals",
    tags=["rentals"],
)

@router.post("/", response_model=RentalRead, status_code=status.HTTP_201_CREATED)
def create_rental(
    rental_in: RentalCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # 1. Lego set létezik és publikus?
    lego_set = db.get(LegoSet, rental_in.lego_set_id)
    if not lego_set:
        raise HTTPException(status_code=404, detail="Lego set not found.")
    if not lego_set.public:
        raise HTTPException(status_code=403, detail="This set is not available for rent.")

    # 2. Nem saját készletet bérel?
    if lego_set.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot rent your own set.")

    # 3. Dátum validáció
    if rental_in.end_date < rental_in.start_date:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date.")
    if rental_in.start_date < date.today():
        raise HTTPException(status_code=400, detail="start_date cannot be in the past.")

    # 4. Van availability erre az időszakra?
    avail_stmt = select(Availability).where(
        Availability.lego_set_id == rental_in.lego_set_id,
        Availability.start_date <= rental_in.start_date,
        Availability.end_date >= rental_in.end_date,
    )
    availability = db.exec(avail_stmt).first()
    if not availability:
        raise HTTPException(
            status_code=400,
            detail="Set is not available for the requested period.",
        )

    # 5. Nincs ütköző aktív rental?
    active_statuses = [
        RentalStatus.REQUESTED,
        RentalStatus.ACCEPTED,
        RentalStatus.IN_PROGRESS,
        RentalStatus.RETURN_PENDING,
    ]
    conflict_stmt = select(Rental).where(
        Rental.lego_set_id == rental_in.lego_set_id,
        Rental.status.in_(active_statuses),
        Rental.start_date <= rental_in.end_date,
        Rental.end_date >= rental_in.start_date,
    )
    conflict = db.exec(conflict_stmt).first()
    if conflict:
        raise HTTPException(
            status_code=400,
            detail="Set is already rented for overlapping dates.",
        )

    # 6. Ár számítás (napok * rental_price)
    days = (rental_in.end_date - rental_in.start_date).days + 1
    total_price = lego_set.rental_price * days

    # 7. Rental létrehozása
    rental = Rental(
        lego_set_id=rental_in.lego_set_id,
        renter_id=current_user.id,
        start_date=rental_in.start_date,
        end_date=rental_in.end_date,
        total_price=total_price,
        status=RentalStatus.REQUESTED,
    )

    db.add(rental)
    db.commit()
    db.refresh(rental)

    return RentalRead(
        id=rental.id,
        lego_set_id=rental.lego_set_id,
        renter_id=rental.renter_id,
        start_date=rental.start_date,
        end_date=rental.end_date,
        total_price=rental.total_price,
        status=rental.status,
        created_at=rental.created_at,
        updated_at=rental.updated_at,
    )
    #--Helper
def check_rental_access(rental: Rental, current_user: User, require_owner: bool = False):
    """Ellenőrzi, hogy a user jogosult-e a rental-hez."""
    is_renter = rental.renter_id == current_user.id
    is_owner = rental.lego_set.owner_id == current_user.id
    is_admin = current_user.role == "ADMIN"

    if require_owner:
        if not (is_owner or is_admin):
            raise HTTPException(status_code=403, detail="Only the owner can perform this action.")
    else:
        if not (is_renter or is_owner or is_admin):
            raise HTTPException(status_code=403, detail="Not authorized for this rental.")

    return is_renter, is_owner, is_admin

# Accept (owner)
@router.patch("/{rental_id}/accept", response_model=RentalRead)
def accept_rental(
    rental_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    rental = db.get(Rental, rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found.")

    check_rental_access(rental, current_user, require_owner=True)

    if rental.status != RentalStatus.REQUESTED:
        raise HTTPException(status_code=400, detail="Can only accept REQUESTED rentals.")

    rental.status = RentalStatus.ACCEPTED
    rental.updated_at = datetime.utcnow()
    db.add(rental)
    db.commit()
    db.refresh(rental)

    return RentalRead(
        id=rental.id,
        lego_set_id=rental.lego_set_id,
        renter_id=rental.renter_id,
        start_date=rental.start_date,
        end_date=rental.end_date,
        total_price=rental.total_price,
        status=rental.status,
        created_at=rental.created_at,
        updated_at=rental.updated_at,
    )

#Start (owner or renter)

@router.patch("/{rental_id}/start", response_model=RentalRead)
def start_rental(
    rental_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    rental = db.get(Rental, rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found.")

    check_rental_access(rental, current_user)

    if rental.status != RentalStatus.ACCEPTED:
        raise HTTPException(status_code=400, detail="Can only start ACCEPTED rentals.")

    rental.status = RentalStatus.IN_PROGRESS
    rental.updated_at = datetime.utcnow()
    db.add(rental)
    db.commit()
    db.refresh(rental)

    return RentalRead(
        id=rental.id,
        lego_set_id=rental.lego_set_id,
        renter_id=rental.renter_id,
        start_date=rental.start_date,
        end_date=rental.end_date,
        total_price=rental.total_price,
        status=rental.status,
        created_at=rental.created_at,
        updated_at=rental.updated_at,
    )

# Request Return (renter)
@router.patch("/{rental_id}/request-return", response_model=RentalRead)
def request_return(
    rental_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    rental = db.get(Rental, rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found.")

    is_renter, _, _ = check_rental_access(rental, current_user)
    if not is_renter:
        raise HTTPException(status_code=403, detail="Only the renter can request return.")

    if rental.status != RentalStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Can only request return for IN_PROGRESS rentals.")

    rental.status = RentalStatus.RETURN_PENDING
    rental.updated_at = datetime.utcnow()
    db.add(rental)
    db.commit()
    db.refresh(rental)

    return RentalRead(
        id=rental.id,
        lego_set_id=rental.lego_set_id,
        renter_id=rental.renter_id,
        start_date=rental.start_date,
        end_date=rental.end_date,
        total_price=rental.total_price,
        status=rental.status,
        created_at=rental.created_at,
        updated_at=rental.updated_at,
    )

#Complete (owner)
@router.patch("/{rental_id}/complete", response_model=RentalRead)
def complete_rental(
    rental_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    rental = db.get(Rental, rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found.")

    check_rental_access(rental, current_user, require_owner=True)

    if rental.status != RentalStatus.RETURN_PENDING:
        raise HTTPException(status_code=400, detail="Can only complete RETURN_PENDING rentals.")

    rental.status = RentalStatus.COMPLETED
    rental.updated_at = datetime.utcnow()
    db.add(rental)
    db.commit()
    db.refresh(rental)

    return RentalRead(
        id=rental.id,
        lego_set_id=rental.lego_set_id,
        renter_id=rental.renter_id,
        start_date=rental.start_date,
        end_date=rental.end_date,
        total_price=rental.total_price,
        status=rental.status,
        created_at=rental.created_at,
        updated_at=rental.updated_at,
    )

#Cancel (renter vagy owner)
@router.patch("/{rental_id}/cancel", response_model=RentalRead)
def cancel_rental(
    rental_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    rental = db.get(Rental, rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found.")

    check_rental_access(rental, current_user)

    # Csak REQUESTED vagy ACCEPTED állapotot lehet törölni
    if rental.status not in [RentalStatus.REQUESTED, RentalStatus.ACCEPTED]:
        raise HTTPException(
            status_code=400,
            detail="Can only cancel REQUESTED or ACCEPTED rentals.",
        )

    rental.status = RentalStatus.CANCELLED
    rental.updated_at = datetime.utcnow()
    db.add(rental)
    db.commit()
    db.refresh(rental)

    return RentalRead(
        id=rental.id,
        lego_set_id=rental.lego_set_id,
        renter_id=rental.renter_id,
        start_date=rental.start_date,
        end_date=rental.end_date,
        total_price=rental.total_price,
        status=rental.status,
        created_at=rental.created_at,
        updated_at=rental.updated_at,
    )
# app/routers/rentals.py
# ... (korábbi importok és POST /rentals, PATCH endpointok)

@router.get("/", response_model=List[RentalRead])
def list_rentals(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    status_filter: RentalStatus | None = None,
    as_renter: bool | None = None,
    as_owner: bool | None = None,
):
    """
    Listázza a current user rental-jait:
    - as_renter=True: ahol ő a bérlő
    - as_owner=True: ahol ő a set tulajdonosa
    - ha egyik sincs megadva: mindkettő (saját bérlései + saját setjeinek bérlései)
    - status_filter: opcionális szűrés státusz szerint
    """
    stmt = select(Rental)

    # Jogosultság: user látja, ahol renter vagy owner
    if as_renter and not as_owner:
        stmt = stmt.where(Rental.renter_id == current_user.id)
    elif as_owner and not as_renter:
        stmt = stmt.join(LegoSet).where(LegoSet.owner_id == current_user.id)
    else:
        # mindkettő: renter VAGY owner
        stmt = stmt.outerjoin(LegoSet).where(
            (Rental.renter_id == current_user.id) | (LegoSet.owner_id == current_user.id)
        )

    # Státusz szűrés
    if status_filter:
        stmt = stmt.where(Rental.status == status_filter)

    rentals = db.exec(stmt).all()

    response: List[RentalRead] = []
    for r in rentals:
        response.append(
            RentalRead(
                id=r.id,
                lego_set_id=r.lego_set_id,
                renter_id=r.renter_id,
                start_date=r.start_date,
                end_date=r.end_date,
                total_price=r.total_price,
                status=r.status,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
        )
    return response


@router.get("/{rental_id}", response_model=RentalRead)
def get_rental(
    rental_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Egy rental részletei.
    Csak a renter, owner vagy admin érheti el.
    """
    rental = db.get(Rental, rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found.")

    # Jogosultság ellenőrzés
    is_renter = rental.renter_id == current_user.id
    is_owner = rental.lego_set.owner_id == current_user.id
    is_admin = current_user.role == "ADMIN"

    if not (is_renter or is_owner or is_admin):
        raise HTTPException(status_code=403, detail="Not authorized to view this rental.")

    return RentalRead(
        id=rental.id,
        lego_set_id=rental.lego_set_id,
        renter_id=rental.renter_id,
        start_date=rental.start_date,
        end_date=rental.end_date,
        total_price=rental.total_price,
        status=rental.status,
        created_at=rental.created_at,
        updated_at=rental.updated_at,
    )

