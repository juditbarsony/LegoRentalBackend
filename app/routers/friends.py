from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models import User, UserFriend
from app.schemas import UserOut
from app.routers.auth import get_current_user

router = APIRouter(
    prefix="/friends",
    tags=["friends"],
)

@router.post("/{friend_id}", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def add_friend(
    friend_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current user ID is missing",
        )

    if friend_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot add yourself as a friend",
        )

    friend = session.get(User, friend_id)
    if not friend:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    existing = session.get(
        UserFriend,
        (current_user.id, friend_id),
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Friend already added",
        )

    friendship = UserFriend(
        user_id=current_user.id,
        friend_id=friend_id,
    )
    session.add(friendship)
    session.commit()

    return friend


@router.get("", response_model=list[UserOut])
def get_friends(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current user ID is missing",
        )

    statement = (
        select(User)
        .join(UserFriend, User.id == UserFriend.friend_id)
        .where(UserFriend.user_id == current_user.id)
    )

    friends = session.exec(statement).all()
    return friends


@router.delete("/{friend_id}")
def delete_friend(
    friend_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current user ID is missing",
        )

    friendship = session.get(UserFriend, (current_user.id, friend_id))
    if not friendship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friend relationship not found",
        )

    session.delete(friendship)
    session.commit()

    return {"message": "Friend removed successfully"}
