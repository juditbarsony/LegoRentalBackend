from pydantic import BaseModel, EmailStr
from typing import Optional, List
from app.models import UserBase
from datetime import datetime
from sqlmodel import SQLModel, Field

# We can inherit from UserBase to avoid duplication
class UserCreate(UserBase):
    password: str

class UserOut(UserBase):
    id: int

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None


# --- LEGO SET SCHEMAS ---

class LegoSetBase(SQLModel):
    set_num: Optional[str] = Field(default=None)
    title: Optional[str] = Field(default=None)
    location: str

    rental_price: float = 0.0
    deposit: float = 0.0
    scan_required: bool = False

    state: Optional[str] = Field(default=None)  # "NEW" / "USED" / "TRASH"
    missing_items: Optional[List[str]] = None   # part number lista
    notes: Optional[str] = None

    public: bool = True

class LegoSetCreate(LegoSetBase):
    """
    Legalább az egyik kötelező: set_num vagy title.
    A backend fogja beolvasni a RebrickableSet-et set_num alapján,
    és abból származtatjuk number_of_items-et.
    """

class LegoSetRead(LegoSetBase):
    id: int
    owner_id: int
    created_at: datetime
    number_of_items: Optional[int] = None