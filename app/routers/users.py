from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models import User
from app.schemas import UserOut
from app.routers.auth import get_current_user

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


@router.get("", response_model=list[UserOut])
def list_users(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    statement = select(User).where(User.id != current_user.id)
    users = session.exec(statement).all()
    return users
