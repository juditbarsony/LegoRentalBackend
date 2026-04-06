from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models import Review, Rental, LegoSet, User
from app.schemas import ReviewCreate, ReviewRead
from app.routers.auth import get_current_user

router = APIRouter(
    prefix="/reviews",
    tags=["reviews"],
)

@router.post("/", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
def create_review(
    review_in: ReviewCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    rental = db.get(Rental, review_in.rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found.")

    lego_set = db.get(LegoSet, review_in.lego_set_id)
    if not lego_set:
        raise HTTPException(status_code=404, detail="Lego set not found.")

    if rental.lego_set_id != review_in.lego_set_id:
        raise HTTPException(status_code=400, detail="Rental does not match lego set.")

    if current_user.id == review_in.reviewee_id:
        raise HTTPException(status_code=400, detail="You cannot review yourself.")

    existing = db.exec(
        select(Review).where(
            Review.rental_id == review_in.rental_id,
            Review.reviewer_id == current_user.id,
            Review.reviewee_id == review_in.reviewee_id,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Review already exists for this rental.")

    review = Review(
        rental_id=review_in.rental_id,
        reviewer_id=current_user.id,
        reviewee_id=review_in.reviewee_id,
        lego_set_id=review_in.lego_set_id,
        rating=review_in.rating,
        comment=review_in.comment,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review

@router.get("/user/{user_id}", response_model=List[ReviewRead])
def get_reviews_for_user(
    user_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    reviews = db.exec(
        select(Review).where(Review.reviewee_id == user_id)
    ).all()
    return reviews


